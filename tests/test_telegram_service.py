import pytest
from unittest.mock import MagicMock, patch
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv('FERNET_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('TELEGRAM_API_ID', '12345')
    monkeypatch.setenv('TELEGRAM_API_HASH', 'testhash')
    monkeypatch.setenv('TG_PROXY_HOST', '')
    from postmanager.services.crypto_service import CryptoService
    CryptoService._instance = None


def make_service():
    with patch('postmanager.services.telegram_service.FirebaseService'), \
            patch('postmanager.services.telegram_service.CryptoService'):
        from postmanager.services.telegram_service import TelegramService
        svc = TelegramService.__new__(TelegramService)
        svc.api_id = 12345
        svc.api_hash = 'testhash'
        svc.firebase = MagicMock()
        svc.crypto = MagicMock()
        return svc


# сохранение аккаунта

def test_save_encrypts_session():
    # шифровать session_string перед записью
    svc = make_service()
    svc.crypto.encrypt.return_value = 'enc_sess'
    svc.firebase.db.collection.return_value.document.return_value.update = MagicMock()

    svc.save_account('uid1', {
        'session_string': 'raw_sess',
        'user_id': 1,
        'channels': [],
    })

    svc.crypto.encrypt.assert_called_once_with('raw_sess')
    data = svc.firebase.db.collection.return_value.document.return_value.update.call_args[0][0]
    assert data['tg_account']['session_string'] == 'enc_sess'


def test_save_stores_channels():
    # сохранять каналы в tg_channels на верхнем уровне документа
    svc = make_service()
    svc.crypto.encrypt.return_value = 'enc'
    svc.firebase.db.collection.return_value.document.return_value.update = MagicMock()

    svc.save_account('uid1', {
        'session_string': 'sess',
        'user_id': 1,
        'channels': [
            {'id': '-100123', 'name': 'Мой канал', 'username': 'mychan'},
            {'id': '-100456', 'name': 'Группа', 'username': ''},
        ],
    })

    data = svc.firebase.db.collection.return_value.document.return_value.update.call_args[0][0]
    assert '-100123' in data['tg_channels']
    assert data['tg_channels']['-100123']['name'] == 'Мой канал'
    assert '-100456' in data['tg_channels']


def test_save_empty_channels_saves_empty_dict():
    # возвращать пустой словарь tg_channels, если каналов нет
    svc = make_service()
    svc.crypto.encrypt.return_value = 'enc'
    svc.firebase.db.collection.return_value.document.return_value.update = MagicMock()

    svc.save_account('uid1', {'session_string': 'sess', 'user_id': 1, 'channels': []})

    data = svc.firebase.db.collection.return_value.document.return_value.update.call_args[0][0]
    assert data['tg_channels'] == {}


def test_save_sets_connected_true():
    svc = make_service()
    svc.crypto.encrypt.return_value = 'enc'
    svc.firebase.db.collection.return_value.document.return_value.update = MagicMock()

    svc.save_account('uid1', {'session_string': 'sess', 'user_id': 1, 'channels': []})

    data = svc.firebase.db.collection.return_value.document.return_value.update.call_args[0][0]
    assert data['tg_connected'] is True


# получение аккаунта

def make_doc(connected, session='enc'):
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {
        'tg_connected': connected,
        'tg_account': {'session_string': session, 'user_id': 1, 'phone': ''}
    }
    return doc


def test_get_account_decrypts_session():
    svc = make_service()
    svc.crypto.decrypt.return_value = 'raw_sess'
    svc.firebase.db.collection.return_value.document.return_value.get.return_value = make_doc(True)

    assert svc.get_account('uid1')['session_string'] == 'raw_sess'


def test_get_account_not_connected_returns_none():
    svc = make_service()
    svc.firebase.db.collection.return_value.document.return_value.get.return_value = make_doc(False)
    assert svc.get_account('uid1') is None


def test_get_account_bad_session_returns_none():
    # считать аккаунт недействительным при повреждённой сессии
    svc = make_service()
    svc.crypto.decrypt.return_value = None
    svc.firebase.db.collection.return_value.document.return_value.get.return_value = make_doc(True)
    assert svc.get_account('uid1') is None


# отключение аккаунта

def test_disconnect_sets_connected_false():
    svc = make_service()
    svc.firebase.db.collection.return_value.document.return_value.update = MagicMock()

    with patch('postmanager.services.telegram_service.DELETE_FIELD', 'DELETE', create=True):
        svc.disconnect_account('uid1')

    data = svc.firebase.db.collection.return_value.document.return_value.update.call_args[0][0]
    assert data['tg_connected'] is False


def test_disconnect_removes_channels():
    # удалять tg_channels при отключении
    svc = make_service()
    svc.firebase.db.collection.return_value.document.return_value.update = MagicMock()

    with patch('postmanager.services.telegram_service.DELETE_FIELD', 'DELETE', create=True):
        svc.disconnect_account('uid1')

    data = svc.firebase.db.collection.return_value.document.return_value.update.call_args[0][0]
    assert 'tg_channels' in data

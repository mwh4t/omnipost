import re
import pytest
from unittest.mock import MagicMock, patch
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv('FERNET_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('VK_APP_ID', 'app123')
    monkeypatch.setenv('VK_APP_SECRET', 'secret')
    from postmanager.services.crypto_service import CryptoService
    CryptoService._instance = None


def make_service():
    with patch('postmanager.services.vk_service.FirebaseService'), \
            patch('postmanager.services.vk_service.CryptoService'):
        from postmanager.services.vk_service import VKService
        svc = VKService.__new__(VKService)
        svc.app_id = 'app123'
        svc.app_secret = 'secret'
        svc.firebase = MagicMock()
        svc.crypto = MagicMock()
        return svc


# url авторизации

def test_auth_url_endpoint():
    # использовать vk id, а не устаревший oauth.vk.com
    svc = make_service()
    assert 'id.vk.com/authorize' in svc.get_auth_url('http://localhost/', 'ch')


def test_auth_url_contains_app_id():
    svc = make_service()
    assert 'app123' in svc.get_auth_url('http://localhost/', 'ch')


def test_auth_url_contains_redirect_uri():
    svc = make_service()
    uri = 'http://localhost/api/vk-callback/'
    assert uri in svc.get_auth_url(uri, 'ch')


def test_auth_url_s256_method():
    # использовать s256 для pkce
    svc = make_service()
    assert 'code_challenge_method=s256' in svc.get_auth_url('http://localhost/', 'ch')


# pkce

def test_verifier_length():
    from postmanager.services.vk_service import VKService
    v = VKService.generate_code_verifier()
    assert 43 <= len(v) <= 128


def test_challenge_is_base64url():
    # содержать только допустимые символы base64url в code_challenge
    from postmanager.services.vk_service import VKService
    v = VKService.generate_code_verifier()
    assert re.match(r'^[A-Za-z0-9\-_]+$', VKService.generate_code_challenge(v))


# сохранение аккаунта

def test_save_encrypts_token():
    # шифровать токен перед записью в firestore
    svc = make_service()
    svc.crypto.encrypt.return_value = 'enc'
    svc.firebase.db.collection.return_value.document.return_value.update = MagicMock()

    svc.save_account('uid1', {'user_id': 1, 'access_token': 'raw', 'user_info': {}})

    svc.crypto.encrypt.assert_called_once_with('raw')
    data = svc.firebase.db.collection.return_value.document.return_value.update.call_args[0][0]
    assert data['vk_account']['access_token'] == 'enc'


def test_save_sets_connected_true():
    svc = make_service()
    svc.crypto.encrypt.return_value = 'enc'
    svc.firebase.db.collection.return_value.document.return_value.update = MagicMock()

    svc.save_account('uid1', {'user_id': 1, 'access_token': 'raw', 'user_info': {}})

    data = svc.firebase.db.collection.return_value.document.return_value.update.call_args[0][0]
    assert data['vk_connected'] is True


# получение аккаунта

def make_doc(connected, token='enc'):
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {
        'vk_connected': connected,
        'vk_account': {'access_token': token, 'user_id': 1, 'user_info': {}}
    }
    return doc


def test_get_account_decrypts_token():
    svc = make_service()
    svc.crypto.decrypt.return_value = 'raw'
    svc.firebase.db.collection.return_value.document.return_value.get.return_value = make_doc(True)

    assert svc.get_account('uid1')['access_token'] == 'raw'


def test_get_account_not_connected_returns_none():
    svc = make_service()
    svc.firebase.db.collection.return_value.document.return_value.get.return_value = make_doc(False)
    assert svc.get_account('uid1') is None


def test_get_account_bad_token_returns_none():
    # считать аккаунт недействительным, если расшифровка упала
    svc = make_service()
    svc.crypto.decrypt.return_value = None
    svc.firebase.db.collection.return_value.document.return_value.get.return_value = make_doc(True)
    assert svc.get_account('uid1') is None


def test_get_account_doc_not_exists_returns_none():
    svc = make_service()
    doc = MagicMock()
    doc.exists = False
    svc.firebase.db.collection.return_value.document.return_value.get.return_value = doc
    assert svc.get_account('uid1') is None

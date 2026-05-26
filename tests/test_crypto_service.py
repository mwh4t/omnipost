import pytest
from cryptography.fernet import Fernet


# сбросить синглтон и задать ключ перед каждым тестом
@pytest.fixture(autouse=True)
def env(monkeypatch):
    from postmanager.services.crypto_service import CryptoService
    monkeypatch.setenv('FERNET_KEY', Fernet.generate_key().decode())
    CryptoService._instance = None


def get():
    from postmanager.services.crypto_service import CryptoService
    CryptoService._instance = None
    return CryptoService()


# шифрование и расшифровка

def test_roundtrip():
    # расшифровать зашифрованное значение в исходное
    c = get()
    assert c.decrypt(c.encrypt('my_token')) == 'my_token'


def test_encrypted_differs_from_original():
    # проверять, что результат шифрования не совпадает с исходником
    c = get()
    assert c.encrypt('token') != 'token'


def test_each_encryption_is_unique():
    # добавлять случайный iv — каждый раз получать разный шифртекст
    c = get()
    assert c.encrypt('same') != c.encrypt('same')


def test_long_string():
    # шифровать длинные строки (токены vk/tg) без ошибок
    c = get()
    value = 'vk2.a.' + 'x' * 512
    assert c.decrypt(c.encrypt(value)) == value


def test_unicode():
    # сохранять юникод корректно
    c = get()
    value = 'токен_💬'
    assert c.decrypt(c.encrypt(value)) == value


# граничные случаи

def test_empty_string_passthrough():
    # возвращать пустую строку как есть, не шифровать
    c = get()
    assert c.encrypt('') == ''


def test_decrypt_empty_returns_none():
    # возвращать none при расшифровке пустой строки
    c = get()
    assert c.decrypt('') is None


def test_decrypt_garbage_returns_none():
    # возвращать none без исключения для невалидного токена
    c = get()
    assert c.decrypt('not_a_fernet_token') is None


def test_wrong_key_returns_none(monkeypatch):
    # зашифровать одним ключом, расшифровать другим → получить none
    from postmanager.services.crypto_service import CryptoService
    CryptoService._instance = None
    encrypted = CryptoService().encrypt('secret')

    CryptoService._instance = None
    monkeypatch.setenv('FERNET_KEY', Fernet.generate_key().decode())
    assert CryptoService().decrypt(encrypted) is None


# синглтон

def test_singleton():
    # возвращать один и тот же объект при нескольких вызовах
    from postmanager.services.crypto_service import CryptoService
    CryptoService._instance = None
    assert CryptoService() is CryptoService()


def test_generate_key_valid():
    # принимать сгенерированный ключ в fernet без ошибок
    from postmanager.services.crypto_service import CryptoService
    Fernet(CryptoService.generate_key().encode())

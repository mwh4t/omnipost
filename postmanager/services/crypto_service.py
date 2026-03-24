from cryptography.fernet import Fernet, InvalidToken
from decouple import config


class CryptoService:
    _instance = None
    _fernet = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_fernet()
        return cls._instance

    # инициализация Fernet
    def _init_fernet(self):
        key = config('FERNET_KEY')
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    # шифрование строки
    def encrypt(self, value: str) -> str:
        if not value:
            return value
        return self._fernet.encrypt(value.encode('utf-8')).decode('utf-8')

    # расшифровка строки
    def decrypt(self, value: str) -> str | None:
        if not value:
            return None
        try:
            return self._fernet.decrypt(value.encode('utf-8')).decode('utf-8')
        except (InvalidToken, Exception):
            return None

    # генерация нового ключа
    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode('utf-8')

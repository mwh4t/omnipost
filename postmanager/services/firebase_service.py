# сервис для работы с firebase admin sdk
import firebase_admin
from firebase_admin import credentials, auth, firestore
from decouple import config


# синглтон для работы с firebase
class FirebaseService:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._init_app()
            FirebaseService._initialized = True

    # инициализация firebase app
    def _init_app(self):
        if not firebase_admin._apps:
            cred = credentials.Certificate({
                "type": config('FIREBASE_TYPE'),
                "project_id": config('FIREBASE_PROJECT_ID'),
                "private_key_id": config('FIREBASE_PRIVATE_KEY_ID'),
                "private_key": config('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
                "client_email": config('FIREBASE_CLIENT_EMAIL'),
                "client_id": config('FIREBASE_CLIENT_ID'),
                "auth_uri": config('FIREBASE_AUTH_URI'),
                "token_uri": config('FIREBASE_TOKEN_URI'),
                "auth_provider_x509_cert_url": config('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
                "client_x509_cert_url": config('FIREBASE_CLIENT_X509_CERT_URL'),
                "universe_domain": config('FIREBASE_UNIVERSE_DOMAIN'),
            })
            firebase_admin.initialize_app(cred)

    # клиент firestore
    @property
    def db(self):
        return firestore.client()

    # модуль auth
    @property
    def auth(self):
        return auth

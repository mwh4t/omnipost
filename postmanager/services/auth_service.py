import requests
from dataclasses import dataclass
from decouple import config
from .firebase_service import FirebaseService
from .user_service import UserService


# результат авторизации
@dataclass
class AuthResult:
    success: bool
    uid: str = None
    email: str = None
    error: str = None


# сервис авторизации
class AuthService:
    # маппинг ошибок firebase
    ERROR_MESSAGES = {
        'EMAIL_EXISTS': 'email уже зарегистрирован',
        'EMAIL_NOT_FOUND': 'пользователь не найден',
        'INVALID_PASSWORD': 'неверный пароль',
        'INVALID_LOGIN_CREDENTIALS': 'неверный email или пароль',
        'WEAK_PASSWORD': 'пароль слишком простой (мин. 6 символов)',
        'INVALID_EMAIL': 'неверный формат email',
    }

    def __init__(self):
        self.firebase = FirebaseService()
        self.user_service = UserService()
        self.api_key = config('FIREBASE_WEB_API_KEY')

    # регистрация через email и пароль
    def register(self, email: str, password: str) -> AuthResult:
        url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={self.api_key}'
        return self._auth_request(url, email, password, 'password')

    # вход через email и пароль
    def login(self, email: str, password: str) -> AuthResult:
        url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.api_key}'
        return self._auth_request(url, email, password, 'password')

    # запрос авторизации к firebase rest api
    def _auth_request(self, url: str, email: str, password: str, provider: str) -> AuthResult:
        try:
            response = requests.post(url, json={
                'email': email,
                'password': password,
                'returnSecureToken': True,
            })

            data = response.json()

            if response.status_code != 200:
                error_code = data.get('error', {}).get('message', 'ошибка авторизации')
                error_message = self.ERROR_MESSAGES.get(error_code, error_code)
                return AuthResult(success=False, error=error_message)

            uid = data.get('localId')

            # сохранение пользователя в firestore
            self.user_service.save(uid=uid, email=email, provider=provider)

            return AuthResult(success=True, uid=uid, email=email)

        except Exception as e:
            return AuthResult(success=False, error=str(e))

    # авторизация через google oauth
    def google_auth(self, code: str, redirect_uri: str) -> AuthResult:
        client_id = config('GOOGLE_WEB_CLIENT_ID')
        client_secret = config('GOOGLE_CLIENT_SECRET')

        try:
            # обмен code на токены
            token_response = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code',
                }
            )

            if token_response.status_code != 200:
                return AuthResult(success=False, error='token_exchange_failed')

            tokens = token_response.json()
            id_token = tokens.get('id_token')

            if not id_token:
                return AuthResult(success=False, error='no_id_token')

            # получение информации о пользователе
            userinfo_response = requests.get(
                f'https://oauth2.googleapis.com/tokeninfo?id_token={id_token}'
            )

            if userinfo_response.status_code != 200:
                return AuthResult(success=False, error='userinfo_failed')

            user_info = userinfo_response.json()
            email = user_info.get('email')
            google_uid = user_info.get('sub')

            # создание или получение пользователя в firebase auth
            try:
                firebase_user = self.firebase.auth.get_user_by_email(email)
            except self.firebase.auth.UserNotFoundError:
                firebase_user = self.firebase.auth.create_user(email=email)

            # сохранение в firestore
            self.user_service.save(
                uid=firebase_user.uid,
                email=email,
                provider='google.com',
                google_uid=google_uid
            )

            return AuthResult(success=True, uid=firebase_user.uid, email=email)

        except Exception as e:
            return AuthResult(success=False, error=str(e))

    # получение url для редиректа на google oauth
    @staticmethod
    def get_google_auth_url(redirect_uri: str) -> str:
        client_id = config('GOOGLE_WEB_CLIENT_ID')
        scope = 'email profile openid'

        return (
            f'https://accounts.google.com/o/oauth2/v2/auth?'
            f'client_id={client_id}&'
            f'redirect_uri={redirect_uri}&'
            f'response_type=code&'
            f'scope={scope}&'
            f'access_type=offline&'
            f'prompt=consent'
        )

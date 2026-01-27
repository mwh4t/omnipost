import vk_api
import secrets
import hashlib
import base64
from dataclasses import dataclass
from decouple import config
from .firebase_service import FirebaseService


@dataclass
class VKAuthResult:
    success: bool
    user_id: int = None
    access_token: str = None
    error: str = None


# сервис авторизации vk
class VKService:
    def __init__(self):
        self.firebase = FirebaseService()
        self.app_id = config('VK_APP_ID')
        self.app_secret = config('VK_APP_SECRET')

    # генерация code_verifier для pkce
    @staticmethod
    def generate_code_verifier() -> str:
        return secrets.token_urlsafe(64)[:128]

    # генерация code_challenge из code_verifier
    @staticmethod
    def generate_code_challenge(code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')

    @staticmethod
    def generate_device_id() -> str:
        return ''

    # получение url для редиректа на vk oauth
    def get_auth_url(self, redirect_uri: str, code_challenge: str) -> str:
        return (
            f'https://id.vk.com/authorize?'
            f'client_id={self.app_id}&'
            f'redirect_uri={redirect_uri}&'
            f'response_type=code&'
            f'scope=vkid.personal_info+email&'
            f'state=vk_auth&'
            f'code_challenge={code_challenge}&'
            f'code_challenge_method=s256'
        )

    # обмен code на access_token
    def auth_callback(self, code: str, redirect_uri: str, code_verifier: str, device_id: str) -> VKAuthResult:
        try:
            import requests

            # vk id endpoint для получения токена
            response = requests.post(
                'https://id.vk.com/oauth2/auth',
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'code_verifier': code_verifier,
                    'client_id': self.app_id,
                    'device_id': device_id,
                    'redirect_uri': redirect_uri,
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )

            # проверка на пустой ответ
            if not response.text or response.text.startswith('<!'):
                return VKAuthResult(success=False, error=f'vk_error_{response.status_code}')

            try:
                data = response.json()
            except Exception:
                return VKAuthResult(success=False, error='vk_invalid_response')

            if 'error' in data:
                return VKAuthResult(
                    success=False,
                    error=data.get('error_description', data.get('error', 'vk_auth_failed'))
                )

            access_token = data.get('access_token')
            user_id = data.get('user_id')

            if not access_token:
                return VKAuthResult(success=False, error='no_access_token')

            return VKAuthResult(
                success=True,
                user_id=user_id,
                access_token=access_token
            )

        except Exception as e:
            return VKAuthResult(success=False, error=str(e))

    # получение информации о пользователе vk
    def get_user_info(self, access_token: str) -> dict | None:
        try:
            vk_session = vk_api.VkApi(token=access_token)
            vk = vk_session.get_api()

            user_info = vk.users.get(fields='photo_100,screen_name')[0]

            return {
                'vk_id': user_info['id'],
                'first_name': user_info.get('first_name', ''),
                'last_name': user_info.get('last_name', ''),
                'screen_name': user_info.get('screen_name', ''),
                'photo': user_info.get('photo_100', ''),
            }

        except Exception:
            return None

    # # получение групп пользователя
    # def get_admin_groups(self, access_token: str) -> list:
    #     try:
    #         vk_session = vk_api.VkApi(token=access_token)
    #         vk = vk_session.get_api()
    #
    #         groups = vk.groups.get(filter='admin', extended=1)
    #
    #         return [
    #             {
    #                 'id': group['id'],
    #                 'name': group['name'],
    #                 'screen_name': group['screen_name'],
    #                 'photo': group.get('photo_100', ''),
    #             }
    #             for group in groups.get('items', [])
    #         ]
    #
    #     except Exception:
    #         return []

    # сохранение vk аккаунта в firestore
    def save_account(self, uid: str, vk_data: dict) -> bool:
        try:
            doc_ref = self.firebase.db.collection('users').document(uid)

            doc_ref.update({
                'vk_connected': True,
                'vk_account': {
                    'user_id': vk_data['user_id'],
                    'access_token': vk_data['access_token'],
                    'user_info': vk_data.get('user_info', {}),
                }
            })

            return True

        except Exception:
            return False

    # отключение vk аккаунта
    def disconnect_account(self, uid: str) -> bool:
        try:
            from google.cloud.firestore_v1 import DELETE_FIELD

            doc_ref = self.firebase.db.collection('users').document(uid)

            doc_ref.update({
                'vk_connected': False,
                'vk_account': DELETE_FIELD,
            })

            return True

        except Exception:
            return False

    # получение vk аккаунта пользователя
    def get_account(self, uid: str) -> dict | None:
        try:
            doc = self.firebase.db.collection('users').document(uid).get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            return data.get('vk_account') if data.get('vk_connected') else None

        except Exception:
            return None

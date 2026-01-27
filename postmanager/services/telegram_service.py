import asyncio
from dataclasses import dataclass
from decouple import config
from telethon import TelegramClient
from telethon.sessions import StringSession
from .firebase_service import FirebaseService


@dataclass
class TGAuthResult:
    success: bool
    session_string: str = None
    user_id: int = None
    phone: str = None
    error: str = None


# сервис авторизации tg
class TelegramService:
    def __init__(self):
        self.firebase = FirebaseService()
        self.api_id = int(config('TELEGRAM_API_ID'))
        self.api_hash = config('TELEGRAM_API_HASH')

    # создание нового клиента с пустой сессией
    def _create_client(self, session_string: str = '') -> TelegramClient:
        return TelegramClient(
            StringSession(session_string),
            self.api_id,
            self.api_hash
        )

    # отправка кода подтверждения на телефон
    async def _send_code_async(self, phone: str) -> dict:
        client = self._create_client()

        try:
            await client.connect()

            result = await client.send_code_request(phone)

            # сохраняем сессию для последующего использования
            session_string = client.session.save()

            return {
                'success': True,
                'phone_code_hash': result.phone_code_hash,
                'session_string': session_string,
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }

        finally:
            await client.disconnect()

    # синхронная обёртка для отправки кода
    def send_code(self, phone: str) -> dict:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(self._send_code_async(phone))
        finally:
            loop.close()

    # авторизация с кодом подтверждения
    async def _sign_in_async(
            self,
            phone: str,
            code: str,
            phone_code_hash: str,
            session_string: str,
            password: str = None
    ) -> TGAuthResult:
        client = self._create_client(session_string)

        try:
            await client.connect()

            try:
                user = await client.sign_in(
                    phone=phone,
                    code=code,
                    phone_code_hash=phone_code_hash
                )
            except Exception as e:
                # 2fa
                if 'password' in str(e).lower() or 'two-step' in str(e).lower():
                    if password:
                        user = await client.sign_in(password=password)
                    else:
                        return TGAuthResult(
                            success=False,
                            error='2fa_required'
                        )
                else:
                    raise e

            # сохранение авторизованной сессии
            final_session = client.session.save()

            return TGAuthResult(
                success=True,
                session_string=final_session,
                user_id=user.id,
                phone=phone
            )

        except Exception as e:
            return TGAuthResult(success=False, error=str(e))

        finally:
            await client.disconnect()

    # синхронная обёртка для авторизации
    def sign_in(
            self,
            phone: str,
            code: str,
            phone_code_hash: str,
            session_string: str,
            password: str = None
    ) -> TGAuthResult:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(
                self._sign_in_async(phone, code, phone_code_hash, session_string, password)
            )
        finally:
            loop.close()

    # получение информации о пользователе
    async def _get_me_async(self, session_string: str) -> dict | None:
        client = self._create_client(session_string)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                return None

            me = await client.get_me()

            return {
                'user_id': me.id,
                'first_name': me.first_name or '',
                'last_name': me.last_name or '',
                'username': me.username or '',
                'phone': me.phone or '',
            }

        except Exception:
            return None

        finally:
            await client.disconnect()

    # синхронная обёртка для получения информации
    def get_me(self, session_string: str) -> dict | None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(self._get_me_async(session_string))
        finally:
            loop.close()

    # # получение каналов где пользователь админ
    # async def _get_admin_channels_async(self, session_string: str) -> list:
    #     client = self._create_client(session_string)
    #
    #     try:
    #         await client.connect()
    #
    #         if not await client.is_user_authorized():
    #             return []
    #
    #         from telethon.tl.functions.channels import GetAdminedPublicChannelsRequest
    #
    #         result = await client(GetAdminedPublicChannelsRequest())
    #
    #         channels = []
    #         for chat in result.chats:
    #             channels.append({
    #                 'id': chat.id,
    #                 'title': chat.title,
    #                 'username': getattr(chat, 'username', ''),
    #             })
    #
    #         return channels
    #
    #     except Exception:
    #         return []
    #
    #     finally:
    #         await client.disconnect()
    #
    # # синхронная обёртка для получения каналов
    # def get_admin_channels(self, session_string: str) -> list:
    #     loop = asyncio.new_event_loop()
    #     asyncio.set_event_loop(loop)
    #
    #     try:
    #         return loop.run_until_complete(self._get_admin_channels_async(session_string))
    #     finally:
    #         loop.close()

    # сохранение tg аккаунта в firestore
    def save_account(self, uid: str, tg_data: dict) -> bool:
        try:
            doc_ref = self.firebase.db.collection('users').document(uid)

            doc_ref.update({
                'tg_connected': True,
                'tg_account': {
                    'session_string': tg_data['session_string'],
                    'user_id': tg_data['user_id'],
                    'phone': tg_data.get('phone', ''),
                    'user_info': tg_data.get('user_info', {}),
                }
            })

            return True

        except Exception:
            return False

    # отключение tg аккаунта
    def disconnect_account(self, uid: str) -> bool:
        try:
            from google.cloud.firestore_v1 import DELETE_FIELD

            doc_ref = self.firebase.db.collection('users').document(uid)

            doc_ref.update({
                'tg_connected': False,
                'tg_account': DELETE_FIELD,
            })

            return True

        except Exception:
            return False

    # получение tg аккаунта пользователя
    def get_account(self, uid: str) -> dict | None:
        try:
            doc = self.firebase.db.collection('users').document(uid).get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            return data.get('tg_account') if data.get('tg_connected') else None

        except Exception:
            return None

import asyncio
from dataclasses import dataclass
from decouple import config
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat
from .firebase_service import FirebaseService
from .crypto_service import CryptoService


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
        self.crypto = CryptoService()
        self.api_id = int(config('TELEGRAM_API_ID'))
        self.api_hash = config('TELEGRAM_API_HASH')

    # создание нового клиента
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
            session_string = client.session.save()

            return {
                'success': True,
                'phone_code_hash': result.phone_code_hash,
                'session_string': session_string,
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

        finally:
            await client.disconnect()

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
                if 'password' in str(e).lower() or 'two-step' in str(e).lower():
                    if password:
                        user = await client.sign_in(password=password)
                    else:
                        return TGAuthResult(success=False, error='2fa_required')
                else:
                    raise e

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

    # получение информации о текущем пользователе
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

    def get_me(self, session_string: str) -> dict | None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._get_me_async(session_string))
        finally:
            loop.close()

    # получение каналов и групп где пользователь является администратором
    async def _get_admin_channels_async(self, session_string: str) -> list:
        client = self._create_client(session_string)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                return []

            channels = []

            # iter_dialogs возвращает все диалоги пользователя
            async for dialog in client.iter_dialogs():
                entity = dialog.entity

                # интересуют только каналы и группы (не личные чаты)
                if not isinstance(entity, (Channel, Chat)):
                    continue

                # проверяем права администратора
                is_admin = False

                if isinstance(entity, Channel):
                    # у каналов и супергрупп проверяем creator или admin_rights
                    if getattr(entity, 'creator', False):
                        is_admin = True
                    elif getattr(entity, 'admin_rights', None):
                        is_admin = True
                elif isinstance(entity, Chat):
                    # для обычных групп проверяем creator или admin_rights
                    if getattr(entity, 'creator', False):
                        is_admin = True
                    elif getattr(entity, 'admin_rights', None):
                        is_admin = True

                if not is_admin:
                    continue

                # формируем id в формате который принимает telethon при отправке
                if isinstance(entity, Channel):
                    channel_id = f'-100{entity.id}'
                else:
                    channel_id = f'-{entity.id}'

                channels.append({
                    'id': channel_id,
                    'name': dialog.name or entity.title,
                    'username': getattr(entity, 'username', '') or '',
                    'is_channel': isinstance(entity, Channel) and getattr(entity, 'broadcast', False),
                })

            return channels

        except Exception as e:
            print(f"Ошибка получения каналов Telegram: {e}")
            return []

        finally:
            await client.disconnect()

    def get_admin_channels(self, session_string: str) -> list:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._get_admin_channels_async(session_string))
        finally:
            loop.close()

    # публикация поста в канал/группу с поддержкой медиагрупп
    async def _publish_async(
            self,
            session_string: str,
            channel_id: str,
            text: str,
            attachments: list = None
    ) -> dict:
        client = self._create_client(session_string)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                return {'success': False, 'error': 'не авторизован'}

            # определяем entity
            if channel_id.startswith('@'):
                entity = channel_id
            else:
                try:
                    entity = int(channel_id)
                except ValueError:
                    entity = channel_id

            if attachments and len(attachments) > 0:
                if len(attachments) == 1:
                    # одно вложение — обычная отправка с подписью
                    message = await client.send_file(
                        entity,
                        attachments[0],
                        caption=text or None,
                        parse_mode='html'
                    )
                    message_id = str(message.id)
                else:
                    # несколько вложений — медиагруппа (альбом)
                    # первый файл получает подпись, остальные без
                    messages = await client.send_file(
                        entity,
                        attachments,
                        caption=text or None,
                        parse_mode='html'
                    )
                    # send_file с несколькими файлами возвращает список
                    if isinstance(messages, list):
                        message_id = str(messages[0].id)
                    else:
                        message_id = str(messages.id)
            else:
                # только текст
                message = await client.send_message(entity, text, parse_mode='html')
                message_id = str(message.id)

            return {'success': True, 'message_id': message_id}

        except Exception as e:
            return {'success': False, 'error': str(e)}

        finally:
            await client.disconnect()

    def publish(
            self,
            session_string: str,
            channel_id: str,
            text: str,
            attachments: list = None
    ) -> dict:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._publish_async(session_string, channel_id, text, attachments)
            )
        finally:
            loop.close()

    # сохранение tg аккаунта и списка каналов в firestore
    def save_account(self, uid: str, tg_data: dict) -> bool:
        try:
            doc_ref = self.firebase.db.collection('users').document(uid)

            encrypted_session = self.crypto.encrypt(tg_data['session_string'])

            # формируем словарь каналов для tg_channels
            channels = tg_data.get('channels', [])
            tg_channels = {
                ch['id']: {'name': ch['name'], 'username': ch.get('username', '')}
                for ch in channels
            }

            doc_ref.update({
                'tg_connected': True,
                'tg_account': {
                    'session_string': encrypted_session,
                    'user_id': tg_data['user_id'],
                    'phone': tg_data.get('phone', ''),
                    'user_info': tg_data.get('user_info', {}),
                },
                'tg_channels': tg_channels,
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
                'tg_channels': DELETE_FIELD,
            })

            return True

        except Exception:
            return False

    # получение tg аккаунта (session_string расшифровывается)
    def get_account(self, uid: str) -> dict | None:
        try:
            doc = self.firebase.db.collection('users').document(uid).get()

            if not doc.exists:
                return None

            data = doc.to_dict()

            if not data.get('tg_connected'):
                return None

            account = data.get('tg_account')
            if not account:
                return None

            encrypted_session = account.get('session_string')
            if encrypted_session:
                decrypted = self.crypto.decrypt(encrypted_session)
                if decrypted:
                    account = dict(account)
                    account['session_string'] = decrypted
                else:
                    return None

            return account

        except Exception:
            return None

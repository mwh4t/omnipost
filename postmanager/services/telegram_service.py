import asyncio
from dataclasses import dataclass
from decouple import config
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat
from .firebase_service import FirebaseService
from .crypto_service import CryptoService
import uuid
import threading
import qrcode
import base64
from io import BytesIO

qr_login_sessions = {}


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
        proxy = None
        proxy_host = config('TG_PROXY_HOST', default='')
        if proxy_host:
            proxy = {
                'proxy_type': 'http',
                'addr': proxy_host,
                'port': int(config('TG_PROXY_PORT', default='1080')),
                'rdns': True,
                'username': config('TG_PROXY_USER', default=None) or None,
                'password': config('TG_PROXY_PASS', default=None) or None,
            }

        return TelegramClient(
            StringSession(session_string),
            self.api_id,
            self.api_hash,
            proxy=proxy,
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

    # авторизация через qr
    def get_qr_login(self) -> dict:
        token = str(uuid.uuid4())
        qr_login_sessions[token] = {'status': 'waiting'}

        def qr_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def workflow():
                client = self._create_client()
                await client.connect()
                try:
                    qr = await client.qr_login()
                    qr_login_sessions[token]['qr_obj'] = qr
                    qr_login_sessions[token]['qr_url'] = qr.url

                    user = None
                    import datetime
                    for _ in range(12):
                        try:
                            user = await qr.wait(10.0)
                            break
                        except asyncio.TimeoutError:
                            now = datetime.datetime.now(tz=datetime.timezone.utc)
                            if (qr.expires - now).total_seconds() < 5:
                                await qr.recreate()

                    if not user:
                        raise Exception("Timeout")

                    qr_login_sessions[token]['status'] = 'success'
                    qr_login_sessions[token]['session_string'] = client.session.save()
                    qr_login_sessions[token]['user_id'] = user.id
                except Exception as e:
                    if 'password' in str(e).lower() or 'two-step' in str(e).lower():
                        qr_login_sessions[token]['status'] = '2fa_required'
                        qr_login_sessions[token]['session_string'] = client.session.save()
                    else:
                        qr_login_sessions[token]['status'] = 'error'
                        qr_login_sessions[token]['error'] = str(e)
                finally:
                    await client.disconnect()

            try:
                loop.run_until_complete(workflow())
            finally:
                loop.close()

        t = threading.Thread(target=qr_thread)
        t.start()

        import time
        for _ in range(50):
            if 'qr_url' in qr_login_sessions[token] or qr_login_sessions[token]['status'] == 'error':
                break
            time.sleep(0.1)

        if 'qr_url' not in qr_login_sessions[token]:
            return {'success': False, 'error': 'FAILED TO GENERATE QR CODE'}

        if qr_login_sessions[token]['status'] == 'error':
            return {'success': False, 'error': qr_login_sessions[token].get('error', 'UNKNOWN ERROR')}

        # генерация qr
        img = qrcode.make(qr_login_sessions[token]['qr_url'])
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return {
            'success': True,
            'token': token,
            'qr_image': f"data:image/png;base64,{img_str}"
        }

    def check_qr_login(self, token: str) -> dict:
        session = qr_login_sessions.get(token)
        if not session:
            return {'status': 'error', 'error': 'THE SESSION WAS NOT FOUND OR EXPIRED'}

        if session['status'] == 'success':
            res = {
                'status': 'success',
                'session_string': session['session_string'],
                'user_id': session['user_id']
            }
            del qr_login_sessions[token]
            return res
        elif session['status'] == '2fa_required':
            return {'status': '2fa_required'}
        elif session['status'] == 'error':
            error = session['error']
            del qr_login_sessions[token]
            return {'status': 'error', 'error': error}
        else:
            res = {'status': 'waiting'}
            qr_obj = session.get('qr_obj')
            if qr_obj and hasattr(qr_obj, 'url'):
                current_url = qr_obj.url
                if current_url and current_url != session.get('qr_url'):
                    session['qr_url'] = current_url
                    import qrcode
                    import base64
                    from io import BytesIO
                    img = qrcode.make(current_url)
                    buffered = BytesIO()
                    img.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    res['qr_image'] = f"data:image/png;base64,{img_str}"
            return res

    def qr_verify_2fa(self, token: str, password: str) -> dict:
        session = qr_login_sessions.get(token)
        if not session or session.get('status') != '2fa_required':
            return {'success': False, 'error': 'INVALID SESSION OR TOKEN'}

        session_string = session['session_string']

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def verify():
            client = self._create_client(session_string)
            await client.connect()
            try:
                user = await client.sign_in(password=password)
                final_session = client.session.save()
                return {'success': True, 'session_string': final_session, 'user_id': user.id}
            except Exception as e:
                return {'success': False, 'error': str(e)}
            finally:
                await client.disconnect()

        try:
            result = loop.run_until_complete(verify())
            if result['success']:
                session['status'] = 'success'
                session['session_string'] = result['session_string']
                session['user_id'] = result['user_id']
            return result
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

    # получение каналов, где пользователь админ
    async def _get_admin_channels_async(self, session_string: str) -> list:
        client = self._create_client(session_string)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                return []

            channels = []

            async for dialog in client.iter_dialogs():
                entity = dialog.entity

                if not isinstance(entity, (Channel, Chat)):
                    continue

                is_admin = False

                if isinstance(entity, Channel):
                    if getattr(entity, 'creator', False):
                        is_admin = True
                    elif getattr(entity, 'admin_rights', None):
                        is_admin = True
                elif isinstance(entity, Chat):
                    if getattr(entity, 'creator', False):
                        is_admin = True
                    elif getattr(entity, 'admin_rights', None):
                        is_admin = True

                if not is_admin:
                    continue

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

    # публикация поста в канал
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

            if channel_id.startswith('@'):
                entity = channel_id
            else:
                try:
                    entity = int(channel_id)
                except ValueError:
                    entity = channel_id

            if attachments and len(attachments) > 0:
                if len(attachments) == 1:
                    message = await client.send_file(
                        entity,
                        attachments[0],
                        caption=text or None,
                        parse_mode='html'
                    )
                    message_id = str(message.id)
                else:
                    messages = await client.send_file(
                        entity,
                        attachments,
                        caption=text or None,
                        parse_mode='html'
                    )
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

    # получение tg аккаунта
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

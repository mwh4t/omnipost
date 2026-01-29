import asyncio
import vk_api
from dataclasses import dataclass
from telethon import TelegramClient
from telethon.sessions import StringSession
from decouple import config
from .firebase_service import FirebaseService
from .vk_service import VKService
from .telegram_service import TelegramService


@dataclass
class PostResult:
    success: bool
    platform: str
    group_id: str
    post_id: str = None
    error: str = None


# сервис публикации постов
class PostService:
    def __init__(self):
        self.firebase = FirebaseService()
        self.vk_service = VKService()
        self.tg_service = TelegramService()

    # публикация поста в Telegram канал
    async def _publish_to_telegram_async(
            self,
            session_string: str,
            channel_id: str,
            text: str,
            attachments: list = None
    ) -> PostResult:
        client = TelegramClient(
            StringSession(session_string),
            int(config('TELEGRAM_API_ID')),
            config('TELEGRAM_API_HASH')
        )

        try:
            await client.connect()

            if not await client.is_user_authorized():
                return PostResult(
                    success=False,
                    platform='telegram',
                    group_id=channel_id,
                    error='не авторизован'
                )

            if channel_id.startswith('@'):
                entity = channel_id
            elif channel_id.startswith('-100'):
                entity = int(channel_id)
            elif channel_id.startswith('-'):
                entity = int(channel_id)
            else:
                # пробуем добавить -100 для публичных каналов
                try:
                    entity = int(f"-100{channel_id}")
                except ValueError:
                    entity = channel_id

            # отправка поста
            if attachments and len(attachments) > 0:
                # отправка с изображениями
                message = await client.send_file(
                    entity,
                    attachments,
                    caption=text if text else None
                )
            else:
                # отправка только текста
                message = await client.send_message(entity, text)

            return PostResult(
                success=True,
                platform='telegram',
                group_id=channel_id,
                post_id=str(message.id)
            )

        except Exception as e:
            return PostResult(
                success=False,
                platform='telegram',
                group_id=channel_id,
                error=str(e)
            )

        finally:
            await client.disconnect()

    # синхронная обёртка для публикации в Telegram
    def publish_to_telegram(
            self,
            session_string: str,
            channel_id: str,
            text: str,
            attachments: list = None
    ) -> PostResult:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(
                self._publish_to_telegram_async(session_string, channel_id, text, attachments)
            )
        finally:
            loop.close()

    # публикация поста во все указанные группы/каналы
    def publish_post(
            self,
            uid: str,
            text: str,
            vk_groups: list[str],
            tg_channels: list[str],
            attachments: list = None
    ) -> dict:
        results = {
            'vk': [],
            'telegram': [],
            'success': True,
            'errors': []
        }

        tg_account = self.tg_service.get_account(uid)

        # публикация в Telegram
        if tg_channels and tg_account:
            session_string = tg_account.get('session_string')

            for channel_id in tg_channels:
                result = self.publish_to_telegram(session_string, channel_id, text, attachments)
                results['telegram'].append(result)

                if not result.success:
                    results['success'] = False
                    results['errors'].append(f"Telegram канал {channel_id}: {result.error}")

        return results

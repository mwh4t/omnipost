import asyncio
import vk_api
from dataclasses import dataclass
from telethon import TelegramClient
from telethon.sessions import StringSession
from decouple import config
from google.cloud.firestore import SERVER_TIMESTAMP
from .firebase_service import FirebaseService
from .vk_service import VKService
from .telegram_service import TelegramService


@dataclass
class PostResult:
    success: bool
    platform: str  # 'vk' или 'telegram'
    group_id: str
    post_id: str = None
    error: str = None


# сервис публикации постов
class PostService:
    def __init__(self):
        self.firebase = FirebaseService()
        self.vk_service = VKService()
        self.tg_service = TelegramService()

    # публикация поста в VK группу
    def publish_to_vk(self, access_token: str, group_id: str, text: str, attachments: list = None) -> PostResult:
        try:
            vk_session = vk_api.VkApi(token=access_token)
            vk = vk_session.get_api()
            upload = vk_api.VkUpload(vk_session)

            # загрузка изображений если есть
            attachment_ids = []
            if attachments:
                for file_path in attachments:
                    try:
                        # загрузка фото на стену группы
                        photo = upload.photo_wall(
                            photos=file_path,
                            group_id=group_id
                        )

                        if photo:
                            # формат: photo{owner_id}_{id}
                            attachment_ids.append(f"photo{photo[0]['owner_id']}_{photo[0]['id']}")
                    except Exception as e:
                        print(f"Ошибка загрузки фото в VK: {e}")
                        continue

            # публикация поста
            post_params = {
                'owner_id': f'-{group_id}',
                'from_group': 1,
                'message': text,
            }

            if attachment_ids:
                post_params['attachments'] = ','.join(attachment_ids)

            response = vk.wall.post(**post_params)

            return PostResult(
                success=True,
                platform='vk',
                group_id=group_id,
                post_id=str(response.get('post_id', ''))
            )

        except Exception as e:
            return PostResult(
                success=False,
                platform='vk',
                group_id=group_id,
                error=str(e)
            )

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

            # форматирование channel_id
            # если начинается с @, оставляем как есть
            # если число, добавляем -100 для супергрупп/каналов
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

        # публикация в VK - используем токены групп
        if vk_groups:
            for group_id in vk_groups:
                # Получаем токен группы
                group_token = self.get_vk_group_token(uid, group_id)

                if not group_token:
                    results['vk'].append(PostResult(
                        success=False,
                        platform='vk',
                        group_id=group_id,
                        error='не найден токен доступа группы'
                    ))
                    results['success'] = False
                    results['errors'].append(f"VK группа {group_id}: не найден токен доступа")
                    continue

                result = self.publish_to_vk(group_token, group_id, text, attachments)
                results['vk'].append(result)

                if not result.success:
                    results['success'] = False
                    results['errors'].append(f"VK группа {group_id}: {result.error}")

        # публикация в Telegram
        if tg_channels:
            tg_account = self.tg_service.get_account(uid)

            if not tg_account:
                results['errors'].append("Telegram не подключен")
                results['success'] = False
            else:
                session_string = tg_account.get('session_string')

                for channel_id in tg_channels:
                    result = self.publish_to_telegram(session_string, channel_id, text, attachments)
                    results['telegram'].append(result)

                    if not result.success:
                        results['success'] = False
                        results['errors'].append(f"Telegram канал {channel_id}: {result.error}")

        return results

    # сохранение токена VK группы
    def save_vk_group_token(self, uid: str, group_id: str, group_token: str) -> bool:
        """Сохранение токена доступа VK группы для пользователя"""
        try:
            doc_ref = self.firebase.db.collection('users').document(uid)
            doc = doc_ref.get()

            # Создаем документ если не существует
            if not doc.exists:
                doc_ref.set({
                    'uid': uid,
                    'vk_groups': {}
                })

            # Получаем текущие группы
            data = doc_ref.get().to_dict()
            vk_groups = data.get('vk_groups', {})

            # Сохраняем токен группы
            vk_groups[group_id] = {
                'token': group_token,
                'added_at': SERVER_TIMESTAMP
            }

            doc_ref.update({
                'vk_groups': vk_groups
            })

            return True

        except Exception as e:
            print(f"Ошибка сохранения токена группы VK: {e}")
            return False

    # получение токена VK группы
    def get_vk_group_token(self, uid: str, group_id: str) -> str | None:
        """Получение токена доступа VK группы"""
        try:
            doc = self.firebase.db.collection('users').document(uid).get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            vk_groups = data.get('vk_groups', {})

            group_data = vk_groups.get(group_id)
            return group_data.get('token') if group_data else None

        except Exception:
            return None

    # удаление токена VK группы
    def remove_vk_group_token(self, uid: str, group_id: str) -> bool:
        """Удаление токена доступа VK группы"""
        try:
            doc_ref = self.firebase.db.collection('users').document(uid)
            doc = doc_ref.get()

            if not doc.exists:
                return False

            data = doc.to_dict()
            vk_groups = data.get('vk_groups', {})

            if group_id in vk_groups:
                del vk_groups[group_id]
                doc_ref.update({
                    'vk_groups': vk_groups
                })

            return True

        except Exception:
            return False

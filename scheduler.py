import os
import sys
import django
from datetime import datetime, timezone
import time

# настройка django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'omnipost.settings')
django.setup()

from postmanager.services import PostService


def process_scheduled_posts():
    post_service = PostService()

    try:
        # получение всех постов
        scheduled_posts_ref = post_service.firebase.db.collection('scheduled_posts') \
            .where('status', '==', 'pending') \
            .stream()

        now = datetime.now(timezone.utc)

        for post_doc in scheduled_posts_ref:
            post_data = post_doc.to_dict()
            post_id = post_doc.id

            # проверка времени публикации
            scheduled_time_str = post_data.get('scheduled_time')
            if not scheduled_time_str:
                continue

            try:
                scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
            except:
                print(f"Ошибка парсинга времени для поста {post_id}")
                continue

            if scheduled_time <= now:
                print(f"Публикация поста {post_id}...")

                # публикация
                results = post_service.publish_post(
                    uid=post_data.get('uid'),
                    text=post_data.get('text', ''),
                    vk_groups=post_data.get('vk_groups', []),
                    tg_channels=post_data.get('tg_channels', []),
                    attachments=post_data.get('attachments')
                )

                # обновление статуса
                if results['success']:
                    post_service.update_scheduled_post_status(post_id, 'published')
                    print(f"Пост {post_id} успешно опубликован")
                else:
                    error_msg = ', '.join(results.get('errors', []))
                    post_service.update_scheduled_post_status(post_id, 'failed', error_msg)
                    print(f"Ошибка публикации поста {post_id}: {error_msg}")

                # удаление временных файлов
                attachments = post_data.get('attachments', [])
                if attachments:
                    for file_path in attachments:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                print(f"Удален временный файл: {file_path}")
                        except Exception as e:
                            print(f"Ошибка удаления файла {file_path}: {e}")

    except Exception as e:
        print(f"Ошибка обработки запланированных постов: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("Запуск планировщика постов...")
    print("Проверка каждые 60 секунд")

    while True:
        try:
            print(f"\n[{datetime.now()}] Проверка запланированных постов...")
            process_scheduled_posts()
            print("Проверка завершена")
        except Exception as e:
            print(f"Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(60)


if __name__ == '__main__':
    main()

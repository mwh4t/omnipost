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
    now = datetime.now(timezone.utc)

    try:
        pending_posts = post_service.get_all_pending_posts()
    except Exception as e:
        print(f"Ошибка получения постов: {e}")
        return

    for post_data in pending_posts:
        post_id = post_data.get('id')

        scheduled_time_str = post_data.get('scheduled_time')
        if not scheduled_time_str:
            continue

        try:
            scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
        except Exception:
            print(f"Ошибка парсинга времени для поста {post_id}")
            continue

        if scheduled_time > now:
            continue

        print(f"Публикация поста {post_id}...")

        try:
            results = post_service.publish_post(
                uid=post_data.get('uid'),
                text=post_data.get('text', ''),
                vk_groups=post_data.get('vk_groups', []),
                tg_channels=post_data.get('tg_channels', []),
                attachments=post_data.get('attachments') or None,
            )

            if results['success']:
                post_service.update_scheduled_post_status(post_id, 'published')
                print(f"Пост {post_id} успешно опубликован")
            else:
                error_msg = ', '.join(results.get('errors', []))
                post_service.update_scheduled_post_status(post_id, 'failed', error_msg)
                print(f"Ошибка публикации поста {post_id}: {error_msg}")

        except Exception as e:
            print(f"Исключение при публикации поста {post_id}: {e}")
            post_service.update_scheduled_post_status(post_id, 'failed', str(e))

        # удаление временных файлов независимо от результата
        for file_path in (post_data.get('attachments') or []):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Ошибка удаления файла {file_path}: {e}")


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

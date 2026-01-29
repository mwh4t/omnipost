from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from decouple import config
import json
import os
from .services import AuthService, VKService, TelegramService, PostService


# redirect uri для vk
VK_REDIRECT_URI = config('VK_REDIRECT_URI')


# главная страница
def home(request):
    user_data = request.session.get('user')
    error = request.GET.get('error')

    # проверка подключенных аккаунтов
    vk_connected = False
    tg_connected = False

    if user_data:
        uid = user_data.get('uid')
        vk_service = VKService()
        tg_service = TelegramService()

        vk_account = vk_service.get_account(uid)
        tg_account = tg_service.get_account(uid)

        vk_connected = vk_account is not None
        tg_connected = tg_account is not None

    context = {
        'social_networks': [
            {'name': 'VK', 'connected': vk_connected},
            {'name': 'Telegram', 'connected': tg_connected},
        ],
        'recent_posts': [],
        'stats': {
            'total_posts': 0,
            'scheduled': 0,
            'published_today': 0,
        },
        'user': user_data,
        'vk_connected': vk_connected,
        'tg_connected': tg_connected,
        'error': error,
    }
    return render(request, 'home.html', context)

# авторизация/регистрация через email и пароль
def email_auth(request):
    if request.method != 'POST':
        return redirect('home')

    email = request.POST.get('email')
    password = request.POST.get('password')
    action = request.POST.get('action', 'login')

    if not email or not password:
        return redirect('/?error=введите email и пароль')

    auth_service = AuthService()

    if action == 'register':
        result = auth_service.register(email, password)
    else:
        result = auth_service.login(email, password)

    if not result.success:
        return redirect(f'/?error={result.error}')

    # сохранение в сессию
    request.session['user'] = {
        'uid': result.uid,
        'email': result.email,
    }

    return redirect('home')

# редирект на google oauth
def google_login(request):
    redirect_uri = request.build_absolute_uri('/api/google-callback/')
    auth_url = AuthService.get_google_auth_url(redirect_uri)
    return redirect(auth_url)

# обработка callback от google oauth
def google_callback(request):
    code = request.GET.get('code')
    error = request.GET.get('error')

    if error:
        return redirect(f'/?error={error}')

    if not code:
        return redirect('/?error=no_code')

    redirect_uri = request.build_absolute_uri('/api/google-callback/')
    auth_service = AuthService()
    result = auth_service.google_auth(code, redirect_uri)

    if not result.success:
        return redirect(f'/?error={result.error}')

    # сохранение в сессию
    request.session['user'] = {
        'uid': result.uid,
        'email': result.email,
    }

    return redirect('home')

# выход из аккаунта
def logout_view(request):
    request.session.flush()
    return redirect('home')

# редирект на vk oauth
def vk_login(request):
    user = request.session.get('user')
    if not user:
        return redirect('/?error=требуется авторизация')

    vk_service = VKService()

    # генерация pkce параметров
    code_verifier = vk_service.generate_code_verifier()
    code_challenge = vk_service.generate_code_challenge(code_verifier)

    # сохранение code_verifier в сессии
    request.session['vk_code_verifier'] = code_verifier

    auth_url = vk_service.get_auth_url(VK_REDIRECT_URI, code_challenge)
    return redirect(auth_url)

# обработка callback от vk oauth
def vk_callback(request):
    user = request.session.get('user')
    if not user:
        return redirect('/?error=требуется_авторизация')

    code = request.GET.get('code')
    device_id = request.GET.get('device_id')
    error = request.GET.get('error')

    if error:
        return redirect(f'/?error=vk_{error}')

    if not code:
        return redirect('/?error=vk_no_code')

    if not device_id:
        return redirect('/?error=vk_no_device_id')

    # получение code_verifier из сессии для vk
    code_verifier = request.session.get('vk_code_verifier')

    if not code_verifier:
        return redirect('/?error=vk_session_expired')

    vk_service = VKService()
    result = vk_service.auth_callback(code, VK_REDIRECT_URI, code_verifier, device_id)

    # очистка временных данных из сессии для vk
    request.session.pop('vk_code_verifier', None)

    if not result.success:
        from urllib.parse import quote
        return redirect(f'/?error={quote(result.error)}')

    # получение информации о пользователе vk
    user_info = vk_service.get_user_info(result.access_token)

    # сохранение в firestore
    vk_service.save_account(user['uid'], {
        'user_id': result.user_id,
        'access_token': result.access_token,
        'user_info': user_info or {},
    })

    return redirect('home')

# отключение vk аккаунта
def vk_disconnect(request):
    user = request.session.get('user')
    if not user:
        return redirect('/?error=требуется авторизация')

    vk_service = VKService()
    vk_service.disconnect_account(user['uid'])

    return redirect('home')

# отправка кода на телефон для tg
def tg_send_code(request):
    user = request.session.get('user')
    if not user:
        return JsonResponse({'success': False, 'error': 'требуется авторизация'})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'method_not_allowed'})

    import json
    try:
        data = json.loads(request.body)
        phone = data.get('phone')
    except:
        phone = request.POST.get('phone')

    if not phone:
        return JsonResponse({'success': False, 'error': 'укажите номер телефона'})

    tg_service = TelegramService()
    result = tg_service.send_code(phone)

    if not result['success']:
        return JsonResponse({'success': False, 'error': result.get('error', 'ошибка отправки кода')})

    # сохранение данных в сессию для tg
    request.session['tg_auth'] = {
        'phone': phone,
        'phone_code_hash': result['phone_code_hash'],
        'session_string': result['session_string'],
    }

    return JsonResponse({'success': True, 'message': 'код отправлен'})

# подтверждение кода для tg
def tg_verify_code(request):
    user = request.session.get('user')
    if not user:
        return JsonResponse({'success': False, 'error': 'требуется авторизация'})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'method_not_allowed'})

    tg_auth = request.session.get('tg_auth')
    if not tg_auth:
        return JsonResponse({'success': False, 'error': 'сначала запросите код'})

    import json
    try:
        data = json.loads(request.body)
        code = data.get('code')
        password = data.get('password')
    except:
        code = request.POST.get('code')
        password = request.POST.get('password')

    if not code:
        return JsonResponse({'success': False, 'error': 'укажите код'})

    tg_service = TelegramService()
    result = tg_service.sign_in(
        phone=tg_auth['phone'],
        code=code,
        phone_code_hash=tg_auth['phone_code_hash'],
        session_string=tg_auth['session_string'],
        password=password
    )

    if not result.success:
        if result.error == '2fa_required':
            return JsonResponse({'success': False, 'error': '2fa_required', 'message': 'требуется пароль 2FA'})
        return JsonResponse({'success': False, 'error': result.error})

    # получение информации о пользователе tg
    user_info = tg_service.get_me(result.session_string)

    # сохранение в firestore
    tg_service.save_account(user['uid'], {
        'session_string': result.session_string,
        'user_id': result.user_id,
        'phone': result.phone,
        'user_info': user_info or {},
    })

    # очистка временных данных
    del request.session['tg_auth']

    return JsonResponse({'success': True, 'message': 'telegram подключен'})

# отключение tg аккаунта
def tg_disconnect(request):
    user = request.session.get('user')
    if not user:
        return redirect('/?error=требуется авторизация')

    tg_service = TelegramService()
    tg_service.disconnect_account(user['uid'])

    return redirect('home')

# публикация поста
def publish_post(request):
    user = request.session.get('user')
    if not user:
        return JsonResponse({'success': False, 'error': 'требуется авторизация'})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'method_not_allowed'})

    # получение данных из формы
    text = request.POST.get('text', '').strip()
    vk_groups_str = request.POST.get('vk_groups', '')
    tg_channels_str = request.POST.get('tg_channels', '')

    # парсинг списков групп/каналов
    vk_groups = [g.strip() for g in vk_groups_str.split(',') if g.strip()]
    tg_channels = [c.strip() for c in tg_channels_str.split(',') if c.strip()]

    # проверка на текст или изображения
    files = request.FILES.getlist('files')
    if not text and not files:
        return JsonResponse({'success': False, 'error': 'добавьте текст или изображение'})

    # проверка на группы/каналы
    if not vk_groups and not tg_channels:
        return JsonResponse({'success': False, 'error': 'укажите хотя бы одну группу или канал'})

    # сохранение загруженных файлов во временную директорию
    saved_files = []
    try:
        for uploaded_file in files:
            # создание временного имени файла
            filename = default_storage.save(
                f'temp/{uploaded_file.name}',
                ContentFile(uploaded_file.read())
            )
            # получение полного путя к файлу
            file_path = default_storage.path(filename)
            saved_files.append(file_path)

        # публикация поста
        post_service = PostService()
        results = post_service.publish_post(
            uid=user['uid'],
            text=text,
            vk_groups=vk_groups,
            tg_channels=tg_channels,
            attachments=saved_files if saved_files else None
        )

        # формирование ответа
        response = {
            'success': results['success'],
            'message': 'пост опубликован' if results['success'] else 'ошибка публикации',
            'vk_results': [
                {
                    'group_id': r.group_id,
                    'success': r.success,
                    'post_id': r.post_id,
                    'error': r.error
                }
                for r in results['vk']
            ],
            'telegram_results': [
                {
                    'channel_id': r.group_id,
                    'success': r.success,
                    'post_id': r.post_id,
                    'error': r.error
                }
                for r in results['telegram']
            ],
            'errors': results['errors']
        }

        return JsonResponse(response)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

    finally:
        # удаление временных файлов
        for file_path in saved_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass

# сохранение токена доступа vk группы
def save_vk_group_token(request):
    user = request.session.get('user')
    if not user:
        return JsonResponse({'success': False, 'error': 'требуется авторизация'})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'method_not_allowed'})

    try:
        data = json.loads(request.body)
        group_id = data.get('group_id', '').strip()
        group_token = data.get('group_token', '').strip()
    except:
        group_id = request.POST.get('group_id', '').strip()
        group_token = request.POST.get('group_token', '').strip()

    if not group_id or not group_token:
        return JsonResponse({'success': False, 'error': 'укажите ID группы и токен доступа'})

    post_service = PostService()
    success = post_service.save_vk_group_token(user['uid'], group_id, group_token)

    if success:
        return JsonResponse({'success': True, 'message': 'токен группы сохранен'})
    else:
        return JsonResponse({'success': False, 'error': 'ошибка сохранения токена'})


# удаление токена доступа vk группы
def remove_vk_group_token(request):
    user = request.session.get('user')
    if not user:
        return JsonResponse({'success': False, 'error': 'требуется авторизация'})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'method_not_allowed'})

    try:
        data = json.loads(request.body)
        group_id = data.get('group_id', '').strip()
    except:
        group_id = request.POST.get('group_id', '').strip()

    if not group_id:
        return JsonResponse({'success': False, 'error': 'укажите ID группы'})

    post_service = PostService()
    success = post_service.remove_vk_group_token(user['uid'], group_id)

    if success:
        return JsonResponse({'success': True, 'message': 'токен группы удален'})
    else:
        return JsonResponse({'success': False, 'error': 'ошибка удаления токена'})


# сохранение tg канала
def save_tg_channel(request):
    user = request.session.get('user')
    if not user:
        return JsonResponse({'success': False, 'error': 'требуется авторизация'})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'method_not_allowed'})

    try:
        data = json.loads(request.body)
        channel_id = data.get('channel_id', '').strip()
        channel_name = data.get('channel_name', '').strip()
    except:
        channel_id = request.POST.get('channel_id', '').strip()
        channel_name = request.POST.get('channel_name', '').strip()

    if not channel_id:
        return JsonResponse({'success': False, 'error': 'укажите ID канала'})

    post_service = PostService()
    success = post_service.save_tg_channel(user['uid'], channel_id, channel_name)

    if success:
        return JsonResponse({'success': True, 'message': 'канал сохранен'})
    else:
        return JsonResponse({'success': False, 'error': 'ошибка сохранения канала'})


# удаление tg канала
def remove_tg_channel(request):
    user = request.session.get('user')
    if not user:
        return JsonResponse({'success': False, 'error': 'требуется авторизация'})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'method_not_allowed'})

    try:
        data = json.loads(request.body)
        channel_id = data.get('channel_id', '').strip()
    except:
        channel_id = request.POST.get('channel_id', '').strip()

    if not channel_id:
        return JsonResponse({'success': False, 'error': 'укажите ID канала'})

    post_service = PostService()
    success = post_service.remove_tg_channel(user['uid'], channel_id)

    if success:
        return JsonResponse({'success': True, 'message': 'канал удален'})
    else:
        return JsonResponse({'success': False, 'error': 'ошибка удаления канала'})


# получение списка сохраненных групп и каналов
def get_saved_groups(request):
    user = request.session.get('user')
    if not user:
        return JsonResponse({'success': False, 'error': 'требуется авторизация'})

    post_service = PostService()

    vk_groups = post_service.get_vk_groups(user['uid'])
    tg_channels = post_service.get_tg_channels(user['uid'])

    vk_list = [
        {'id': group_id, 'name': f"VK Group {group_id}"}
        for group_id in vk_groups.keys()
    ]

    tg_list = [
        {'id': channel_id, 'name': data.get('name', channel_id)}
        for channel_id, data in tg_channels.items()
    ]

    return JsonResponse({
        'success': True,
        'vk_groups': vk_list,
        'tg_channels': tg_list
    })

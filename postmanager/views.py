from django.shortcuts import render, redirect
from .services import AuthService


# главная страница
def home(request):
    user_data = request.session.get('user')
    error = request.GET.get('error')

    context = {
        'social_networks': [
            {'name': 'VK', 'connected': True},
            {'name': 'Telegram', 'connected': True},
        ],
        'recent_posts': [],
        'stats': {
            'total_posts': 0,
            'scheduled': 0,
            'published_today': 0,
        },
        'user': user_data,
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

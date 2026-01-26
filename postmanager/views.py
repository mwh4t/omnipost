from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decouple import config
import json
import requests
from .firebase_utils import verify_token, save_user_to_firestore, init_firebase
from firebase_admin import auth

def home(request):
    # авторизован ли пользователь
    user_data = request.session.get('user')
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
        'firebase_api_key': config('FIREBASE_WEB_API_KEY'),
        'firebase_project_id': config('FIREBASE_PROJECT_ID'),
        'google_client_id': config('GOOGLE_WEB_CLIENT_ID', default=''),
    }
    return render(request, 'home.html', context)

def auth_view(request):
    context = {
        'firebase_api_key': config('FIREBASE_WEB_API_KEY'),
        'firebase_project_id': config('FIREBASE_PROJECT_ID'),
        'google_client_id': config('GOOGLE_WEB_CLIENT_ID', default=''),
    }
    return render(request, 'auth.html', context)

# верификация токена от клиента и сохранение в сессию
@csrf_exempt
def verify_auth(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            id_token = data.get('idToken')

            if not id_token:
                return JsonResponse({'error': 'токен не предоставлен'}, status=400)

            # проверка токена через firebase admin
            decoded_token = verify_token(id_token)

            if decoded_token:
                # сохранение пользователя в firestore
                try:
                    save_user_to_firestore(decoded_token)
                except Exception as firestore_err:
                    print(f"ошибка сохранения в firestore: {firestore_err}")

                # сохранение в сессию
                request.session['user'] = {
                    'uid': decoded_token['uid'],
                    'email': decoded_token.get('email', ''),
                }
                return JsonResponse({'success': True, 'user': request.session['user']})
            else:
                return JsonResponse({'error': 'невалидный токен'}, status=401)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'метод не разрешён'}, status=405)

# выход из аккаунта
def logout_view(request):
    request.session.flush()
    return redirect('home')

# обработка callback от google oauth
def google_callback(request):
    code = request.GET.get('code')
    error = request.GET.get('error')

    if error:
        return redirect('/?error=' + error)

    if not code:
        return redirect('/?error=no_code')

    try:
        # обмен code на токены
        token_url = 'https://oauth2.googleapis.com/token'
        client_id = config('GOOGLE_WEB_CLIENT_ID')
        client_secret = config('GOOGLE_CLIENT_SECRET', default='')
        redirect_uri = request.build_absolute_uri('/api/google-callback/')

        token_response = requests.post(token_url, data={
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        })

        if token_response.status_code != 200:
            print(f"token error: {token_response.text}")
            return redirect('/?error=token_exchange_failed')

        tokens = token_response.json()
        id_token = tokens.get('id_token')

        if not id_token:
            return redirect('/?error=no_id_token')

        # получение информации о пользователе из id_token
        userinfo_url = 'https://oauth2.googleapis.com/tokeninfo'
        userinfo_response = requests.get(f"{userinfo_url}?id_token={id_token}")

        if userinfo_response.status_code != 200:
            return redirect('/?error=userinfo_failed')

        user_info = userinfo_response.json()
        email = user_info.get('email')
        uid = user_info.get('sub')

        # создание или получение пользователя в firebase
        init_firebase()
        try:
            firebase_user = auth.get_user_by_email(email)
        except auth.UserNotFoundError:
            firebase_user = auth.create_user(email=email, uid=uid)

        # сохранение в firestore
        try:
            from .firebase_utils import get_firestore_client
            from google.cloud.firestore_v1 import SERVER_TIMESTAMP
            db = get_firestore_client()
            db.collection('users').document(firebase_user.uid).set({
                'email': email,
                'provider': 'google.com',
                'created_at': SERVER_TIMESTAMP,
            }, merge=True)
        except Exception as e:
            print(f"firestore error: {e}")

        # сохранение в сессию
        request.session['user'] = {
            'uid': firebase_user.uid,
            'email': email,
        }

        return redirect('home')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return redirect('/?error=auth_failed')

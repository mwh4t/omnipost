import firebase_admin
from firebase_admin import credentials, auth, firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from decouple import config

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": config('FIREBASE_TYPE'),
            "project_id": config('FIREBASE_PROJECT_ID'),
            "private_key_id": config('FIREBASE_PRIVATE_KEY_ID'),
            "private_key": config('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
            "client_email": config('FIREBASE_CLIENT_EMAIL'),
            "client_id": config('FIREBASE_CLIENT_ID'),
            "auth_uri": config('FIREBASE_AUTH_URI'),
            "token_uri": config('FIREBASE_TOKEN_URI'),
            "auth_provider_x509_cert_url": config('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
            "client_x509_cert_url": config('FIREBASE_CLIENT_X509_CERT_URL'),
            "universe_domain": config('FIREBASE_UNIVERSE_DOMAIN'),
        })
        firebase_admin.initialize_app(cred)
    return firebase_admin.get_app()

# возврат клиента firestore
def get_firestore_client():
    init_firebase()
    return firestore.client()

# проверка токенов пользователя
def verify_token(id_token):
    init_firebase()
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        print(f"ошибка верификации токена: {e}")
        return None

# сохранение пользователя в firestore
def save_user_to_firestore(user_data):
    db = get_firestore_client()
    users_ref = db.collection('users')

    # только email и провайдер
    provider = 'unknown'
    if 'firebase' in user_data and 'sign_in_provider' in user_data['firebase']:
        provider = user_data['firebase']['sign_in_provider']

    users_ref.document(user_data['uid']).set({
        'email': user_data.get('email', ''),
        'provider': provider,
        'created_at': SERVER_TIMESTAMP,
    }, merge=True)

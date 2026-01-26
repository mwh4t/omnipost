# сервис для работы с пользователями в firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from .firebase_service import FirebaseService


# работа с пользователями
class UserService:
    COLLECTION = 'users'

    def __init__(self):
        self.firebase = FirebaseService()

    # сохранение пользователя в firestore
    def save(self, uid: str, email: str, provider: str, **extra_data) -> dict:
        user_data = {
            'uid': uid,
            'email': email,
            'provider': provider,
            'created_at': SERVER_TIMESTAMP,
            **extra_data
        }

        self.firebase.db.collection(self.COLLECTION).document(uid).set(
            user_data,
            merge=True
        )

        return user_data

    # получение пользователя по uid
    def get(self, uid: str) -> dict | None:
        doc = self.firebase.db.collection(self.COLLECTION).document(uid).get()
        return doc.to_dict() if doc.exists else None

    # получение пользователя по email
    def get_by_email(self, email: str) -> dict | None:
        docs = self.firebase.db.collection(self.COLLECTION).where(
            'email', '==', email
        ).limit(1).get()

        for doc in docs:
            return doc.to_dict()
        return None

    # удаление пользователя
    def delete(self, uid: str) -> bool:
        self.firebase.db.collection(self.COLLECTION).document(uid).delete()
        return True

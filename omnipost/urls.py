from django.contrib import admin
from django.urls import path
from postmanager import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('api/email-auth/', views.email_auth, name='email_auth'),
    path('api/google-login/', views.google_login, name='google_login'),
    path('api/google-callback/', views.google_callback, name='google_callback'),
    path('logout/', views.logout_view, name='logout'),

    # vk авторизация
    path('api/vk-login/', views.vk_login, name='vk_login'),
    path('api/vk-callback/', views.vk_callback, name='vk_callback'),
    path('api/vk-disconnect/', views.vk_disconnect, name='vk_disconnect'),

    # tg авторизация
    path('api/tg-send-code/', views.tg_send_code, name='tg_send_code'),
    path('api/tg-verify-code/', views.tg_verify_code, name='tg_verify_code'),
    path('api/tg-disconnect/', views.tg_disconnect, name='tg_disconnect'),
]

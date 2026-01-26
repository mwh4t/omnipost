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
]

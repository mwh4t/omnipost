from django.contrib import admin
from django.urls import path
from postmanager import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('auth/', views.auth_view, name='auth'),
    path('api/verify-auth/', views.verify_auth, name='verify_auth'),
    path('api/google-callback/', views.google_callback, name='google_callback'),
    path('logout/', views.logout_view, name='logout'),
]

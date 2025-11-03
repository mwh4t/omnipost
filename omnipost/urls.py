from django.contrib import admin
from django.urls import path
from postmanager import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('auth/', views.auth_view, name='auth'),
]

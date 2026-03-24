from django.urls import path
from . import auth_views

urlpatterns = [
    path('login/', auth_views.auth_login, name='auth_login'),
    path('callback/', auth_views.auth_callback, name='auth_callback'),
    path('logout/', auth_views.auth_logout, name='auth_logout'),
]

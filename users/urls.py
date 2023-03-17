from django.urls import path, re_path
from django.conf.urls import url

from . import views


app_name = 'users'


urlpatterns = [
    path('logout', views.logout, name='logout'),
    path("login/", views.login, name='login'),
    path("register", views.register, name="register"),
    path('password', views.password_change, name='password_change'),

    ]
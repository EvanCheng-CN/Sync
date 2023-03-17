# coding: utf-8

from django.urls import path, re_path
from django.conf.urls import url

from . import views


app_name = 'tasks'


urlpatterns = [
    path('', views.index, name='index'),
    path('api/machines/realtime', views.machine_status, name='machines_status'),
    path('install/ssh/<str:username>', views.install_ssh, name='install_ssh'),
    path('install/check', views.check_ssh, name='check_ssh'),
    path('install', views.install_instruction, name='install_instruction'),
    ]

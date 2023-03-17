# coding: utf-8
from waitress import serve
from syncTasker.wsgi import application


serve(application, host='10.204.14.109', port=1050)

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from .utils import get_client_ip
from .models import Machine, MachineStatus
from supervisor_api import Api as SupervisorApi, api_url as supervisor_url
from django.utils import timezone, dateformat
import pytz


def index(request):
    ls = MachineStatus.objects.all()
    return render(request, 'tasks/index.html', context={
        'title': '欢迎',
        'ls': ls
        })


def machine_status(request):
    ls = MachineStatus.objects.all()
    return JsonResponse(data={
        'machines': [
            {"id": status.pk, "status": status.online, "time": dateformat.format(status.updated_at.astimezone(pytz.timezone(settings.TIME_ZONE)), 'Y-m-d H:i:s')} for status in ls
            ]
        })


def install_instruction(request):
    """安装指南"""
    return render(request, 'tasks/instruction.html', context={
        'title': 'OpenSSH 服务器安装',
        })


def install_ssh(request, username):
    """获取rsa公钥"""
    client_ip = get_client_ip(request)
    machine, ok = Machine.objects.get_or_create(ip=client_ip)
    if ok:
        if machine.user != username:
            machine.user = username
            machine.save()
    return JsonResponse({'pub': machine.rsa_pub, 'user': username})


def check_ssh(request):
    """检测是否正常"""
    client_ip = get_client_ip(request)
    machine = get_object_or_404(klass=Machine, ip=client_ip)

    return JsonResponse({'status': machine.check_auth()})
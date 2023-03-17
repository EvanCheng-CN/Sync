# coding: utf-8
from django.conf import settings
import os
from huey import crontab
from huey.contrib.djhuey import periodic_task, task
from datetime import datetime
from . import models
from django.utils.timezone import localtime
from ssh_tool import SSH2
from datetime import datetime, timedelta
import typing
from pathlib import Path
from simple_logger import make_logger
import os
from .models import Machine, MachineStatus, SyncTask, SyncJob, MachineTaskFile


logger = make_logger('loop-download', log_file=os.path.join(settings.BASE_DIR, 'logs/loop-download.log'))
start = datetime.now()


def get_tasks():
    """获取所有的任务"""
    tasks = {}
    for t in SyncTask.objects.filter(is_active=SyncTask.IsActiveChoices.yes).all():
        if t.period not in tasks:
            tasks[t.period] = []
        tasks[t.period].append(t)
    return tasks


@task()
def dispatch():
    """按照用户设置调度执行任务"""
    tasks = get_tasks()
    now = datetime.now()
    d: timedelta = now - start
    minutes = int(d.total_seconds() / 60)
    for n, ls in tasks.items():
        if minutes % n == 0 and ls:
            logger.info(f'【任务周期{n}分钟】有{len(ls)}个任务待处理')
            for t in ls:
                handle_task(tid=t.id)


@task()
def handle_task(tid: int):
    """
    处理一个同步任务
    :param tid: 任务的id
    :return:
    """
    t = SyncTask.objects.filter(id=tid).first()
    if t is None:
        return
    ip = t.machine.ip
    port = 22
    user = t.machine.user
    key = t.machine.rsa_key
    j = SyncJob.objects.create(
        task=t,
        )
    last_one = t.file_records.order_by('-timestamp').first()

    if isinstance(last_one, MachineTaskFile):
        timestamp = last_one.timestamp
    else:
        timestamp = None
    reasons = []
    try:
        ssh = SSH2(host=ip, port=port, user=user, key=key, path=t.path, prefix=t.prefix)
        try:
            ssh.init_connect()
        except (ConnectionRefusedError, ConnectionResetError, ConnectionResetError, ConnectionAbortedError):
            reasons.append('网络连接失败')
            raise
        try:
            r = ssh.authenticate()
        except:
            reasons.append('ssh鉴权失败')
            raise
        if not r:
            reasons.append('认证未通过')
            raise ValueError('ssh鉴权失败')
        if not ssh.check_remote_path_exist():
            reasons.append('远程文件夹不存在')
            raise ValueError('远程文件夹不存在')
        try:
            files = ssh.get_files(timestamp=timestamp)
        except:
            reasons.append('获取远程文件列表失败')
            raise
        if not files:
            j.status = SyncJob.StatusChoices.success
            j.detail = '没有查询到符合的文件，可能所有文件已经全部下载回来'
            j.save()
            logger.info(f'【任务{t}】, {j.detail}')
            return
        target_dir = Path(settings.MACHINE_FILES_LOCATION) / f'{ip}_{t.prefix}'
        try:
            ssh.download_files(files=files, target_dir=target_dir)
        except:
            reasons.append('下载文件失败')
            raise
        max_timestamp = max([file_timestamp for file_name, file_timestamp, file_size in files])
        m_file = MachineTaskFile.objects.create(task=t,
            file='|'.join([file_name for file_name, file_timestamp, file_size in files]), timestamp=max_timestamp)
        j.status = SyncJob.StatusChoices.success
        j.file = m_file
        j.save()
        logger.info(f'【任务{t}】, 有{len(files)}个文件待下载')
    except:
        pass
    if reasons:
        j.status = SyncJob.StatusChoices.fialed
        j.detail = ';'.join(reasons)
        j.save()
        logger.warning(f'【任务{t}】, {j.detail}')
    else:
        j.status = SyncJob.StatusChoices.success
        j.save()
        logger.info(f'【任务{t}】, 任务成功')


@periodic_task(crontab(minute='*'))
def task_checker():
    """
    每两分钟发现一次任务，并分配执行
    :return:
    """
    logger.info('【例行检查任务】')
    dispatch()

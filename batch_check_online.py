# coding: utf-8
import time
import django
from datetime import datetime
import threading
import os
from simple_logger import make_logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'syncTasker.settings')
django.setup()
from django.conf import settings

logger = make_logger(name='Batch Check Online', log_file=settings.BASE_DIR / 'logs/batch_check.log')

"""
批量检测主机是否在线
"""

from tasks.models import Machine, MachineStatus


def get_now():
    return datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')


def batch_check():
    logger.info('\n')
    logger.info('='*30)
    logger.info('开始扫描')
    for m in Machine.objects.all():
        r = m.status.check_in_online()
        logger.info(f'{m} {["离线", "在线"][r]}')
    logger.info('本次扫描结束')
    logger.info('='*30)


class ScanThread(threading.Thread):
    def run(self):
        batch_check()


def block():
    task = ScanThread()
    task.setDaemon(True)

    while 1:
        if task.is_alive():
            logger.warning('【警告】一个执行周期内没有完成扫描')
            continue
        else:
            task = ScanThread()
            task.setDaemon(True)
            task.start()
        time.sleep(10)


if __name__ == '__main__':
    block()

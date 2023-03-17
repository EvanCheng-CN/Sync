from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models.signals import post_save
from django.conf import settings
from .utils import check_tcp_service, generate_keys
from ssh_tool import SSH2
from pathlib import Path
import zipfile
import io
import typing


class Machine(models.Model):
    """客户机"""
    ip = models.GenericIPAddressField(verbose_name='IP地址', null=False, blank=False, unique=True, db_index=True)
    user = models.CharField(verbose_name='用户名', max_length=128, blank=False, null=False, default='admin')
    alias = models.CharField(verbose_name='主机别名', max_length=128, null=True, blank=True)
    rsa_key = models.TextField(verbose_name='RSA 私钥', null=True, blank=True)
    rsa_pub = models.TextField(verbose_name='RSA 公钥', null=True, blank=True)

    created_at = models.DateTimeField(verbose_name='创建于', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新于', auto_now=True)

    def __str__(self):
        return self.alias if self.alias else self.ip

    class Meta:
        ordering = ['-created_at', '-updated_at']
        verbose_name = '客户机'
        verbose_name_plural = '主机管理'

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.rsa_key:
            pub, key = generate_keys()
            self.rsa_key = key.decode()
            self.rsa_pub = pub.decode()
        return super(Machine, self).save(
            force_insert=force_insert, force_update=force_update, using=using,
            update_fields=update_fields)

    def check_auth(self) -> bool:
        host = self.ip
        user = self.user
        port = 22
        key = self.rsa_key
        if SSH2.check_tcp_service(host=host, port=port):
            ssh = SSH2(host=host, port=port, user=user, path='', prefix='', key=key)
            try:
                ssh.init_connect()
                if ssh.authenticate():
                    return True
            except:
                pass

        return False


class SyncTask(models.Model):
    """同步任务"""
    machine = models.ForeignKey(to=Machine, on_delete=models.CASCADE, related_name='task_ls', null=False, blank=False, verbose_name='所属主机')  # 外键
    path = models.CharField(verbose_name='任务文件夹', max_length=255, null=False, blank=False, default='C:\\report\\', help_text=r'举例 C:\report\ -- 远程客户机上的绝对路径')
    prefix = models.CharField(verbose_name='', max_length=32, null=False, blank=False, default='EVT', help_text=r'（实际上没有用这个参数， 默认就好）举例 C:\report\ 下的成对的文件是 EVT2020091801.csv 和 2020091801.csv， 填写 EVT')
    period = models.PositiveIntegerField(verbose_name='周期（分钟）', validators=[MaxValueValidator(150), MinValueValidator(1)], help_text='每隔多少分钟执行一次任务')  # 执行间隔的周期

    class IsActiveChoices(models.IntegerChoices):
        yes = 1, '已批准'
        no = 0, '已停止'

    is_active = models.PositiveSmallIntegerField(verbose_name='任务状态', choices=IsActiveChoices.choices, default=IsActiveChoices.yes, help_text='改变状态时，当前正在开展的任务不受影响，下一轮任务才会受影响')

    created_at = models.DateTimeField(verbose_name='创建于', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新于', auto_now=True)

    class Meta:
        ordering = ['machine', '-created_at', '-updated_at']
        verbose_name = '任务'
        verbose_name_plural = '任务管理'

    def __str__(self):
        return f'{self.machine} {self.path} 前缀 {self.prefix}'

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        name = f'{self.machine.ip}_{self.prefix}'

        return super(SyncTask, self).save(
            force_insert=force_insert, force_update=force_update, using=using,
            update_fields=update_fields)


class MachineStatus(models.Model):
    """客户机的在线状态"""
    class OnlineChoices(models.IntegerChoices):
        online = 1, '在线'
        offline = 0, '不在线'

    machine = models.OneToOneField(
        to=Machine, on_delete=models.CASCADE, related_name='status', null=False,
        blank=False, primary_key=True, verbose_name='主机')  # 外键
    online = models.SmallIntegerField(verbose_name='是否在线', choices=OnlineChoices.choices, default=OnlineChoices.online, null=False, blank=False)

    created_at = models.DateTimeField(verbose_name='创建于', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新于', auto_now=True)

    class Meta:
        ordering = ['-created_at', '-updated_at']
        verbose_name = '主机状态'
        verbose_name_plural = '在线监控'

    def check_in_online(self):
        ip = self.machine.ip
        port = 22
        r = check_tcp_service(host=ip, port=port)
        self.online = int(r)
        self.save()
        return r

    def __str__(self):
        return f'{self.machine} 在线状态'


class MachineTaskFile(models.Model):
    """任务文件"""
    task = models.ForeignKey(to=SyncTask, on_delete=models.CASCADE, null=False, blank=False, verbose_name='所属任务', related_name='file_records')
    file = models.TextField(verbose_name='相关文件名称', null=False, blank=False)  # 不带前缀的文件名
    timestamp = models.IntegerField(verbose_name='远程时间戳', null=False, blank=False)  # 文件时间戳

    class ProcessedChoices(models.IntegerChoices):
        no = 0, '没有'
        yes = 1, '完成'

    is_processed = models.SmallIntegerField(
        verbose_name='进一步处理', choices=ProcessedChoices.choices,
        default=ProcessedChoices.no, null=False, blank=False,
        help_text='“进一步处理”指是否对下载回来的数据进一步处理，比如分析，打包发送到其他服务器')

    created_at = models.DateTimeField(verbose_name='创建于', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新于', auto_now=True)

    class Meta:
        ordering = ['-created_at', '-updated_at']
        verbose_name = '任务文件'
        verbose_name_plural = '文件监视'

    @property
    def all_file_name_ls(self) -> typing.List[str]:
        """该次任务相关的文件名列表"""
        ls = self.file.split('|')
        return ls

    @property
    def all_file_path(self) -> typing.List[Path]:
        """获取服务器上相关文件的绝对路径"""
        filenames = self.all_file_name_ls
        ip = self.task.machine.ip
        files_dir = Path(settings.MACHINE_FILES_LOCATION) / f'{ip}_{self.task.prefix}'
        return [files_dir / fn for fn in filenames]

    def get_zip_content(self) -> bytes:
        """
        获取服务器上相关文件压缩文件后的内容，content，数据类型是 bytes
        保存为文件的方法是
        with open('1.zip', 'wb') as h:
            h.write(content)
        """
        # todo 分组
        file = io.BytesIO()

        zip_file = zipfile.ZipFile(file, 'w')

        for fp in self.all_file_path:
            zip_file.write(fp, arcname=fp.name)

        zip_file.close()

        file.seek(0)
        return file.read()

    def __str__(self):
        return f'{self.task}相关文件'


class SyncJob(models.Model):
    """任务记录"""
    class StatusChoices(models.IntegerChoices):
        processing = 0, '执行中'
        success = 1, '成功'
        fialed = 2, '失败'

    task = models.ForeignKey(to=SyncTask, on_delete=models.CASCADE, null=False, blank=False, related_name='job_ls')
    status = models.SmallIntegerField(verbose_name='任务状态', choices=StatusChoices.choices, default=StatusChoices.processing, null=False, blank=False)
    file = models.OneToOneField(to=MachineTaskFile, on_delete=models.CASCADE, related_name='job', null=True, blank=True)
    detail = models.CharField(verbose_name='任务详情', max_length=128, null=True, blank=True)

    created_at = models.DateTimeField(verbose_name='创建于', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新于', auto_now=True)

    class Meta:
        ordering = ['-created_at', '-updated_at']
        verbose_name = '同步记录'
        verbose_name_plural = '任务日志'

    def __str__(self):
        return f'任务开始于 {self.created_at.strftime("%Y-%m-%d %H:%M:%S")}'


def get_recent_jobs(ins: SyncTask):
    """"""
    ongoing = ins.job_ls.filter(status=SyncJob.StatusChoices.processing).first()
    if ongoing:
        return 


def create_machine_status_model(sender, instance: Machine, **kwargs):
    """"""
    MachineStatus.objects.get_or_create(machine_id=instance.id)


post_save.connect(create_machine_status_model, sender=Machine)

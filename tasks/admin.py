from django.contrib import admin
from django.utils.html import format_html
from . import models


@admin.register(models.SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = 'task', 'status', 'created_at', 'updated_at'


class SyncJobInline(admin.TabularInline):
    model = models.SyncJob
    fields = 'task', 'status', 'created_at', 'updated_at'
    readonly_fields = 'created_at', 'updated_at'
    extra = 0


@admin.register(models.MachineStatus)
class MachineStatus(admin.ModelAdmin):
    list_display = 'machine', 'online', 'updated_at'
    readonly_fields = 'machine', 'online', 'updated_at', 'created_at'


@admin.register(models.SyncTask)
class SyncTaskAdmin(admin.ModelAdmin):
    list_display = 'machine',  'prefix', 'path', 'period', 'is_active', 'created_at'
    inlines = SyncJobInline,


class SyncTaskInline(admin.TabularInline):
    model = models.SyncTask
    fields = 'path', 'prefix', 'period', 'created_at', 'updated_at', 'extra_option'
    readonly_fields = 'created_at', 'updated_at', 'extra_option'
    extra = 0

    def extra_option(self, instance: models.SyncTask):
        # todo 增加功能
        return '待添加'


@admin.register(models.Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = 'id', 'ip', 'user', 'alias', 'online_status', 'created_at', 'updated_at',
    list_display_links = 'ip',
    readonly_fields = 'created_at', 'updated_at', 'rsa_key', 'rsa_pub', 'online_status'

    inlines = SyncTaskInline,

    def online_status(self, instance: models.Machine):
        return ['离线', '在线'][instance.status.online]

    online_status.short_description = '是否在线'

    fields = 'ip', 'user', 'alias', 'online_status', 'rsa_key', 'rsa_pub', 'created_at', 'updated_at',


@admin.register(models.MachineTaskFile)
class MachineTaskFileAdmin(admin.ModelAdmin):
    list_display = 'task', 'timestamp', 'created_at', 'updated_at',
    # exclude = 'file',

    fields = 'task', 'timestamp', 'file', 'files_on_server', 'is_processed', 'created_at', 'updated_at',
    readonly_fields = 'created_at', 'updated_at', 'files_on_server', 'is_processed'

    def files_on_server(self, instance: models.MachineTaskFile):
        files = instance.all_file_name_ls
        html = f'<ol><li>{"</li><li>".join(files)}</li></ol>'
        return format_html(html)

    files_on_server.short_description = '文件列表'

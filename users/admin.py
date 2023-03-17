# coding: utf-8
from django.contrib import admin
from django import forms
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = 'id', 'username', 'email'
    list_display_links = 'username',
    readonly_fields = 'last_login',
    fields = 'username', 'email', 'password', 'is_superuser', 'is_staff', 'is_active', 'groups', 'user_permissions'

    def save_model(self, request, obj: User, form: forms.Form, change: bool):
        if 'password' in form.changed_data:
            obj.set_password(obj.password)
            obj.save()
        return super(UserAdmin, self).save_model(request, obj, form, change)


admin.site.site_header = "数据管理后台"
admin.site.site_title = "数据管理后台"
admin.site.index_title = "数据管理后台"

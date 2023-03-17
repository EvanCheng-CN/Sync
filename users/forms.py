# coding: utf-8

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordResetForm as __PasswordResetForm
from django.utils.translation import gettext_lazy as _
import re

from . import models


def email_check(email):
    pattern = re.compile(r"\"?([-a-zA-Z0-9.`?{}]+@\w+\.\w+)\"?")
    return re.match(pattern, email)


class MyUserCreationForm(UserCreationForm):

    class Meta:
        model = models.User
        fields = ('username', 'email',)


class LoginForm(forms.Form):

    username = forms.CharField(label=_('username'), max_length=50)
    password = forms.CharField(label=_('Password'), widget=forms.PasswordInput)

    # Use clean methods to define custom validation rules

    def clean_username(self):
        username = self.cleaned_data.get('username')

        if email_check(username):
            filter_result = models.User.objects.filter(email__exact=username)
            if not filter_result:
                raise forms.ValidationError("This email does not exist.")
        else:
            filter_result = models.User.objects.filter(username__exact=username)
            if not filter_result:
                raise forms.ValidationError("This username does not exist. Please register first.")

        return username


class PasswordResetForm(__PasswordResetForm):

    def clean_email(self):
        email = self.cleaned_data.get('email', '')

        filter_result = models.User.objects.filter(email__exact=email)
        if not filter_result:
            raise forms.ValidationError("This email does not exist.")
        print(email)
        return email
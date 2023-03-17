from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import (auth, messages)
from django.http import (HttpResponse, HttpResponseRedirect, HttpResponseNotFound,
                         HttpResponseNotAllowed, JsonResponse, HttpResponseServerError)
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import User
from .forms import (
    MyUserCreationForm, LoginForm, PasswordResetForm)

from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import Group
from .decrators import anonymous_required


@anonymous_required
def login(request):
    next_ = request.GET.get('next')
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = auth.authenticate(username=username, password=password)
            if user is not None and user.is_active:
                auth.login(request, user)
                if user.is_superuser:
                    return redirect('/admin')
                if next_:
                    return redirect(next_)
                else:
                    return redirect('/')
            else:
                messages.warning(request, '用户名或者密码错误')
    else:
        form = LoginForm()

    return render(request, 'users/login.html', {'form': form, 'title': '用户登录'})


def register(request):
    if request.method == 'POST':

        form = MyUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            return redirect(reverse('users:login'))
    else:
        form = MyUserCreationForm()

    return render(request, 'users/register.html', {'form': form, 'title': '用户注册'})


@login_required
def logout(request):
    print('logout')
    auth.logout(request)
    return HttpResponseRedirect(reverse('users:login'))


@login_required
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, '您的密码已更新')
            return redirect('users:password_change')
        else:
            messages.error(request, '密码更新失败')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'users/password_change.html', {'form': form, 'title': '修改密码'})
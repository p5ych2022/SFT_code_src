# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

# 注册自定义User模型到Admin，并使用UserAdmin以显示和编辑常规用户字段
admin.site.register(User, UserAdmin)

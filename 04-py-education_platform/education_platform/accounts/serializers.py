# accounts/serializers.py
from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # 返回的字段（不包含密码）
        fields = ['id', 'username', 'email', 'phone', 'is_teacher']

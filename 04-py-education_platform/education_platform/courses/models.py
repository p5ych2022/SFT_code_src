from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """自定义用户模型，增加角色字段"""
    # 是否为教师角色（True表示教师，False表示学生）
    is_teacher = models.BooleanField(default=False)

    # 扩展用户字段，如手机号
    phone = models.CharField(max_length=20, blank=True, null=True, unique=True, verbose_name="手机号")

    def __str__(self):
        return self.username
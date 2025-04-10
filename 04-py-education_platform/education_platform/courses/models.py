# courses/models.py

from django.db import models
from django.conf import settings

class Category(models.Model):
    """课程分类"""
    name = models.CharField(max_length=50, unique=True, verbose_name="分类名称")

    def __str__(self):
        return self.name

class Course(models.Model):
    """课程模型"""
    title = models.CharField(max_length=100, verbose_name="课程标题")
    description = models.TextField(blank=True, verbose_name="课程简介")
    outline = models.TextField(blank=True, verbose_name="课程大纲")  # 可以存储JSON或纯文本
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="分类")
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="教师")
    # 可选：课程封面或课件文件上传
    material = models.FileField(upload_to="course_materials/", null=True, blank=True, verbose_name="课件文件")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.teacher.username})"

class CoursePurchase(models.Model):
    """课程购买/订单模型"""
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="学生")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="课程")
    purchase_time = models.DateTimeField(auto_now_add=True, verbose_name="购买时间")
    # 支付状态：未支付、已支付
    PAID_STATUS = (
        ('pending', '未支付'),
        ('paid', '已支付'),
        ('canceled', '已取消'),
    )
    status = models.CharField(max_length=10, choices=PAID_STATUS, default='pending', verbose_name="支付状态")
    order_id = models.CharField(max_length=100, blank=True, verbose_name="订单号")      # 微信支付订单号/流水号
    transaction_id = models.CharField(max_length=100, blank=True, verbose_name="交易流水号")  # 第三方支付平台交易ID

    class Meta:
        unique_together = ('student', 'course')  # 防止重复购买同一课程

    def __str__(self):
        return f"{self.student.username} - {self.course.title} ({self.status})"

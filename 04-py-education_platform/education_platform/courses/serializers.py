# courses/serializers.py
from rest_framework import serializers
from .models import Course, Category, CoursePurchase

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class CourseSerializer(serializers.ModelSerializer):
    # 嵌套序列化教师用户名和分类名称
    teacher_name = serializers.CharField(source='teacher.username', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'outline', 'category', 'category_name',
                  'teacher', 'teacher_name', 'material']

class CoursePurchaseSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    class Meta:
        model = CoursePurchase
        fields = ['id', 'student', 'course', 'purchase_time', 'status']
        read_only_fields = ['student', 'purchase_time', 'status']

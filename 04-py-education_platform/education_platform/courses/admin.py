# courses/admin.py
from django.contrib import admin
from .models import Course, Category, CoursePurchase

admin.site.register(Category)
admin.site.register(Course)
admin.site.register(CoursePurchase)

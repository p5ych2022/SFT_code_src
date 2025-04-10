# courses/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CourseViewSet, CategoryViewSet, PurchaseAPIView, course_list_page

# 使用DRF路由器注册视图集
router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'categories', CategoryViewSet, basename='category')

urlpatterns = [
    # 课程列表、详情、创建等接口 (courses/)
    path('', include(router.urls)),
    # 课程购买接口 (purchase/)
    path('purchase/', PurchaseAPIView.as_view({'post': 'create'}), name='purchase'),
    path('courses_page/', course_list_page, name='courses_page')
]
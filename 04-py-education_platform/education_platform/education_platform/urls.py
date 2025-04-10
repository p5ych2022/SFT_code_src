# education_platform/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),    # 用户注册、登录相关接口
    path('api/', include('courses.urls')),          # 课程和购买相关接口
    # 可选：添加一个主页或课程列表页面
    path('', include('courses.urls')),  # 将课程列表视图作为首页（简单处理）
]

# 开发环境下提供媒体文件的访问（生产环境应由Nginx等服务器处理）
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

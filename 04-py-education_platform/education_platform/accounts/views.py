# accounts/views.py

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework import status, permissions

User = get_user_model()

class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """用户注册接口：接受用户名或邮箱或手机号，密码，角色"""
        data = request.data
        username = data.get('username') or data.get('email') or data.get('phone')
        password = data.get('password')
        email = data.get('email', '')
        phone = data.get('phone', '')
        is_teacher = data.get('is_teacher', False)

        if not username or not password:
            return JsonResponse({'error': '用户名(邮箱/手机号)和密码为必填项'}, status=400)
        # 检查用户名是否已存在
        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': '用户已存在'}, status=400)
        # 创建用户
        user = User.objects.create_user(username=username, password=password, email=email)
        # 如果提供了手机号，保存手机号并设置用户名为手机号（或自行处理逻辑）
        if phone:
            user.phone = phone
        # 设置角色
        user.is_teacher = True if str(is_teacher).lower() == 'true' else False
        user.save()
        return JsonResponse({'message': '注册成功', 'user': {
            'id': user.id, 'username': user.username, 'is_teacher': user.is_teacher
        }}, status=201)

class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """用户登录接口：接受用户名或邮箱或手机号 + 密码"""
        data = request.data
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return JsonResponse({'error': '必须提供用户名和密码'}, status=400)
        # 支持用邮箱或手机号登录：尝试通过邮箱或手机号找到用户名
        user_obj = None
        if '@' in username:
            try:
                user_obj = User.objects.get(email=username)
                username = user_obj.username  # 获取实际用户名用于认证
            except User.DoesNotExist:
                user_obj = None
        elif username.isdigit():
            try:
                user_obj = User.objects.get(phone=username)
                username = user_obj.username
            except User.DoesNotExist:
                user_obj = None
        # 使用用户名进行认证
        user = authenticate(request, username=username, password=password)
        if user is None:
            return JsonResponse({'error': '用户名或密码错误'}, status=401)
        # 登录用户（建立session）
        login(request, user)
        return JsonResponse({'message': '登录成功', 'user': {
            'id': user.id, 'username': user.username, 'is_teacher': user.is_teacher
        }}, status=200)

class LogoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """用户注销接口"""
        logout(request)
        return JsonResponse({'message': '已注销'}, status=200)

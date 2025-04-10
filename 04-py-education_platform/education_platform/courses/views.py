# courses/views.py

from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions
from .models import Course, Category, CoursePurchase
from .serializers import CourseSerializer, CategorySerializer, CoursePurchaseSerializer

class CourseViewSet(viewsets.ModelViewSet):
    """课程视图集：提供列出、检索、创建课程功能"""
    queryset = Course.objects.select_related('teacher', 'category').all()
    serializer_class = CourseSerializer

    def get_permissions(self):
        # 非安全方法需要认证，创建需要教师权限
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated()]
        else:
            # 列表、检索允许任何人访问查看
            return [permissions.AllowAny()]

    def list(self, request, *args, **kwargs):
        """列出课程，可按分类过滤，并做简单缓存"""
        # 尝试从缓存获取课程列表数据
        category_id = request.query_params.get('category')
        cache_key = f"course_list_{category_id or 'all'}"
        data = cache.get(cache_key)
        if data:
            return JsonResponse({'courses': data}, safe=False)

        # 未缓存则查询数据库
        queryset = self.filter_queryset(self.get_queryset())
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        courses = self.get_serializer(queryset, many=True).data
        cache.set(cache_key, courses, 60)  # 缓存1分钟
        return JsonResponse({'courses': courses}, status=200)

    def create(self, request, *args, **kwargs):
        """创建课程（仅教师）"""
        if not request.user.is_authenticated:
            return HttpResponseForbidden("需要先登录")
        if not request.user.is_teacher:
            return HttpResponseForbidden("只有教师用户可以创建课程")
        # 设置 teacher 为当前用户
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(teacher=request.user)
        return JsonResponse({'message': '课程创建成功', 'course': serializer.data}, status=201)

    # retrieve, update, destroy 直接使用父类实现 (可选定制权限/逻辑)
    # def retrieve(self, request, *args, **kwargs):
    #     return super().retrieve(request, *args, **kwargs)

class CategoryViewSet(viewsets.ModelViewSet):
    """课程分类 视图集（可选，实现增删改查分类）"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAdminUser]  # 分类管理仅管理员可操作

class PurchaseAPIView(viewsets.ViewSet):
    """课程购买接口：学生购买课程，调用微信支付下单"""
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request):
        # 提取课程ID并获取课程
        course_id = request.data.get('course_id')
        course = get_object_or_404(Course, id=course_id)
        user = request.user
        if user.is_teacher:
            return JsonResponse({'error': '教师不能购买课程'}, status=400)
        # 检查是否已购买过
        purchase, created = CoursePurchase.objects.get_or_create(student=user, course=course)
        if not created:
            if purchase.status == 'paid':
                return JsonResponse({'message': '您已购买过此课程'}, status=200)
            # 如果之前有未支付的订单，可以选择重新发起支付或提示
        # 调用微信支付统一下单接口
        # （此处为简化，实际需调用微信API获取支付链接或二维码）
        try:
            # TODO: 集成微信支付API，例如使用 requests 向微信统一下单接口发送请求
            # 示例: response = wechat_unified_order(course, user)
            purchase.order_id = "WX12345"  # 微信订单号 (示例值)
            purchase.status = 'paid'       # 假设直接支付成功，实际应在支付回调中更新
            purchase.transaction_id = "TRANSACTION12345"  # 微信返回的交易流水号 (示例)
            purchase.save()
        except Exception as e:
            return JsonResponse({'error': '支付接口调用失败', 'detail': str(e)}, status=500)
        return JsonResponse({'message': '购买成功', 'course_id': course.id, 'status': purchase.status}, status=200)

def course_list_page(request):
    courses = Course.objects.select_related('teacher','category').all()
    return render(request, 'courses_list.html', {'courses': courses})
# user_manager/views.py
from django.core.mail import send_mail
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from AiInterviewAgent import settings
from django.shortcuts import get_object_or_404
from .models import User, EmailVerificationCode
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    EmailVerificationSerializer
)
from .tokens import email_verification_token
import random
import string
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
# from .authentication import CustomJWTAuthentication
# from .permissions import IsLoggedInOrExempt

class UserRegistrationView(APIView):
    # permission_classes = [IsLoggedInOrExempt]
    permission_classes = [AllowAny]  # 允许匿名访问
    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('verification_code')

        # 验证验证码
        if not email or not code:
            return Response({'error': '请提供邮箱和验证码'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            record = EmailVerificationCode.objects.get(email=email, is_used=False)
            if not record.is_valid():
                return Response({'error': '验证码已过期，请重新获取'}, status=status.HTTP_400_BAD_REQUEST)
            if record.code != code:
                return Response({'error': '验证码错误'}, status=status.HTTP_400_BAD_REQUEST)
        except EmailVerificationCode.DoesNotExist:
            return Response({'error': '验证码不存在或已被使用'}, status=status.HTTP_400_BAD_REQUEST)

        # 验证码验证通过，标记为已使用
        record.is_used = True
        record.save()

        # 验证其他注册信息
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': '注册成功'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    # permission_classes = [IsLoggedInOrExempt]
    permission_classes = [AllowAny]  # 允许匿名访问
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # 正确生成访问令牌和刷新令牌
            access_token = AccessToken.for_user(user)
            refresh_token = RefreshToken.for_user(user)  # 显式生成刷新令牌

            return Response(
                {
                    "access": str(access_token),
                    "refresh": str(refresh_token),  # 使用refresh_token
                    "user_id": user.id
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# 另一种注册方式，目前没有用
class EmailVerificationView(APIView):
    # permission_classes = [IsLoggedInOrExempt]
    permission_classes = [AllowAny]  # 允许匿名访问
    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                uid = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))  # 修改此处
                user = User.objects.get(pk=uid)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                user = None

            if user and email_verification_token.check_token(user, serializer.validated_data['token']):
                user.is_email_verified = True
                user.save()
                return Response({"message": "邮箱验证成功"}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "验证链接无效"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    # authentication_classes = [CustomJWTAuthentication]
    # permission_classes = [IsLoggedInOrExempt]
    permission_classes = [IsAuthenticated]  # 需要认证才能访问
    def get(self, request):
        # 返回用户个人信息
        serializer = UserRegistrationSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SendVerificationCodeView(APIView):
    # permission_classes = [IsLoggedInOrExempt]
    permission_classes = [AllowAny]  # 允许匿名访问
    def post(self, request):
        try:
            email = request.data.get('email')
            if not email:
                return Response({'error': '请提供邮箱地址'}, status=status.HTTP_400_BAD_REQUEST)

            # 生成6位随机数字验证码
            code = ''.join(random.choices(string.digits, k=6))
            expires_at = timezone.now() + timezone.timedelta(minutes=5)
            print(f"生成验证码 {code} 发送至 {email}")

            # 数据库操作
            try:
                record = EmailVerificationCode.objects.get(email=email)
                record.code = code
                record.expires_at = expires_at
                record.is_used = False
                record.save()
            except EmailVerificationCode.DoesNotExist:
                EmailVerificationCode.objects.create(
                    email=email,
                    code=code,
                    expires_at=expires_at
                )

            # 发送邮件（添加详细日志）
            try:
                subject = 'AI面试系统 - 邮箱验证码'
                message = f'您的验证码是：{code}\n有效期5分钟，请不要泄露给他人。\n若与您无关，请忽略'
                # 打印邮件内容到日志（开发环境）
                print(f"邮件内容: {subject}\n{message}")

                # 生产环境发送邮件，开发环境可暂时注释
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )

                return Response({'message': '验证码已发送，请查收邮箱'}, status=status.HTTP_200_OK)

            except Exception as e:
                print(f"邮件发送失败: {str(e)}")
                return Response({'error': '发送邮件失败，请稍后重试'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            return Response({'error': '服务器错误，请稍后重试'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]  # 仅认证用户可访问

    def post(self, request):
        """使当前用户的令牌失效，实现退出登录"""
        try:
            # 获取请求中的刷新令牌
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({'error': '请提供 refresh token'}, status=status.HTTP_400_BAD_REQUEST)

            # 使刷新令牌失效（同时使关联的访问令牌失效）
            token = RefreshToken(refresh_token)
            token.blacklist()  # 将令牌加入黑名单

            return Response({'message': '已成功退出登录'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserDeleteView(APIView):
    # authentication_classes = [CustomJWTAuthentication]
    # permission_classes = [IsLoggedInOrExempt]
    permission_classes = [IsAuthenticated]  # 需要认证才能访问
    def delete(self, request):
        """彻底删除用户账户（增强版）"""
        user_id = request.data.get('user_id', request.user.id)
        password = request.data.get('password')

        # 权限控制
        if not request.user.is_staff and user_id != request.user.id:
            raise PermissionDenied("您没有权限删除其他用户")

        try:
            user = get_object_or_404(User, id=user_id)

            # 超级管理员保护
            if user.is_superuser:
                if request.user != user and not request.user.is_superuser:
                    raise PermissionDenied("只有超级管理员可以删除其他超级管理员")
                if request.user == user:
                    return Response(
                        {"error": "超级管理员不能删除自己"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # 自我删除时验证密码
            if user_id == request.user.id:
                if not password:
                    return Response(
                        {"error": "请提供密码以验证身份"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if not user.check_password(password):
                    return Response(
                        {"error": "密码错误，无法删除账户"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # 清理关联数据
            self.clean_related_data(user)

            # 执行彻底删除
            username = user.username
            user.delete()

            return Response(
                {"message": f"用户 {username} 已被彻底删除"},
                status=status.HTTP_200_OK
            )

        except PermissionDenied as pd:
            return Response({"error": str(pd)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            import traceback
            print(f"删除用户失败: {str(e)}")
            print(traceback.format_exc())
            return Response(
                {"error": f"删除用户失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def clean_related_data(self, user):
        """清理与用户关联的所有数据"""
        # 清理邮箱验证码
        EmailVerificationCode.objects.filter(email=user.email).delete()

        # 清理用户令牌（JWT场景无需处理，Token自动过期）
        # 其他关联数据清理...
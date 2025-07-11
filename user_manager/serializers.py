import re

from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User, EmailVerificationCode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import smart_str, force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from .models import User  # 假设User模型在models.py中


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'email', 'username', 'password', 'confirm_password',
            'major', 'university', 'phone', 'gender', 'name',
            'province', 'city', 'district', 'address', 'ethnicity'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True},
            'name': {'required': True},
            'phone': {'required': True},
        }

    def validate(self, data):
        # 验证邮箱唯一性
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("该邮箱已被注册")

        # 验证手机号唯一性
        if User.objects.filter(phone=data['phone']).exists():
            raise serializers.ValidationError("该手机号已被注册")

        # 验证密码匹配
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("两次输入的密码不一致")

        # 验证手机号格式
        phone_regex = r'^1[3-9]\d{9}$'
        if not re.match(phone_regex, data['phone']):
            raise serializers.ValidationError("手机号格式错误")

        return data

    def create(self, validated_data):
        # 移除确认密码字段，不需要保存到数据库
        validated_data.pop('confirm_password')

        # 获取密码并进行哈希处理
        password = validated_data.pop('password')
        hashed_password = make_password(password)

        # 创建用户并设置哈希后的密码
        user = User.objects.create(
            password=hashed_password,
            **validated_data
        )

        # 生成邮箱验证令牌
        token = PasswordResetTokenGenerator().make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # 这里可以添加发送验证邮件的逻辑

        return user


from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User


class UserLoginSerializer(serializers.Serializer):
    # 移除固定的email字段，改为可选的phone和email（至少提供一个）
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        # 获取用户输入的手机号或邮箱
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password')

        # 验证至少提供了一种认证方式
        if not phone and not email:
            raise serializers.ValidationError("请提供手机号或邮箱进行登录")

        # 根据提供的字段查询用户
        user = None
        if phone:
            try:
                user = User.objects.get(phone=phone)
            except User.DoesNotExist:
                pass
        elif email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                pass

        # 验证用户是否存在并检查密码
        if user is None:
            raise serializers.ValidationError("手机号/邮箱或密码错误")

        # 使用Django内置的check_password方法验证密码
        if not user.check_password(password):
            raise serializers.ValidationError("手机号/邮箱或密码错误")

        # 检查邮箱是否已验证
        if not user.is_email_verified:
            raise serializers.ValidationError("邮箱尚未验证")

        return {'user': user}

class EmailVerificationSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, data):
        try:
            uid = smart_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is None:
            raise serializers.ValidationError("无效的用户ID")

        if not PasswordResetTokenGenerator().check_token(user, data['token']):
            raise serializers.ValidationError("无效的验证令牌")

        return {'user': user}



class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'email', 'username', 'major', 'university', 'phone',
            'gender', 'name', 'province', 'city', 'district',
            'address', 'ethnicity', 'is_email_verified'
        ]
        read_only_fields = ['email', 'is_email_verified']

    def validate_phone(self, value):
        # 验证手机号格式
        phone_regex = r'^1[3-9]\d{9}$'
        if not re.match(phone_regex, value):
            raise serializers.ValidationError("手机号格式错误")

        # 检查手机号唯一性（排除当前用户）
        user = self.context['request'].user
        if User.objects.exclude(pk=user.pk).filter(phone=value).exists():
            raise serializers.ValidationError("该手机号已被其他用户使用")

        return value

    def update(self, instance, validated_data):
        # 更新用户资料
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("该邮箱未注册")
        return value


class PasswordResetSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        # 验证密码匹配
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("两次输入的密码不一致")

        try:
            uid = smart_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is None:
            raise serializers.ValidationError("无效的用户ID")

        if not PasswordResetTokenGenerator().check_token(user, data['token']):
            raise serializers.ValidationError("无效的重置令牌")

        return {'user': user, 'new_password': data['new_password']}
# user_manager/serializers.py
from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'email', 'username', 'password', 'confirm_password',
            'major', 'university', 'phone', 'gender',
        ]

    def validate(self, data):
        # 验证邮箱唯一性
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("该邮箱已被注册")

        # 验证密码匹配
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("两次输入的密码不一致")

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')  # 移除确认密码字段

        # 创建用户但不保存密码（避免明文存储）
        user = User.objects.create(
            email=validated_data['email'],
            username=validated_data['username'],
            major=validated_data.get('major'),
            university=validated_data.get('university'),
            phone=validated_data.get('phone'),
            gender=validated_data.get('gender'),
        )

        # 哈希密码并保存
        user.set_password(validated_data['password'])
        user.save()

        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        # 注意：使用 email 作为 username 字段，因为你的 User 模型使用 email 作为 USERNAME_FIELD
        user = authenticate(
            username=data['email'],  # 关键：使用 email 作为 username
            password=data['password']
        )
        if not user:
            raise serializers.ValidationError("邮箱或密码错误")
        if not user.is_email_verified:
            raise serializers.ValidationError("邮箱尚未验证")
        return {'user': user}


class EmailVerificationSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
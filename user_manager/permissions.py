# user_manager/permissions.py
from rest_framework.permissions import BasePermission
from django.urls import resolve

# 自定义权限类
class IsLoggedInOrExempt(BasePermission):
    def has_permission(self, request, view):
        exempt_paths = [
            'send-verification-code',
            'register',
            'login',
        ]
        resolved = resolve(request.path_info)
        if resolved.url_name in exempt_paths:
            return True

        return bool(request.user and request.user.is_authenticated)
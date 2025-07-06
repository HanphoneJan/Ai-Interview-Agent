# user_manager/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken
from django.utils.translation import gettext_lazy as _

# 自定义认证类
class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except InvalidToken:
            raise AuthenticationFailed(_('无效的 token'), code='token_not_valid')

        return self.get_user(validated_token), validated_token
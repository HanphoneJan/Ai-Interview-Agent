# user_manager/urls.py
from django.urls import path
from .views import (
    UserRegistrationView,
    UserLoginView,
    LogoutView,
    EmailVerificationView,
    UserProfileView, SendVerificationCodeView,
    TokenRefreshView,
    UserDeleteView,
    PasswordResetView
)

urlpatterns = [
    path('send-verification-code/', SendVerificationCodeView.as_view(), name='send-verification-code'),
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('verify-email/', EmailVerificationView.as_view(), name='verify-email'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('delete-user/', UserDeleteView.as_view(), name='delete-user'),
    path('reset-password/', PasswordResetView.as_view(), name='password-reset'),
]
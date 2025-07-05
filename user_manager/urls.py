# user_manager/urls.py
from django.urls import path
from .views import (
    UserRegistrationView,
    UserLoginView,
    EmailVerificationView,
    UserProfileView, SendVerificationCodeView,
    UserDeleteView
)

urlpatterns = [
    path('send-verification-code/', SendVerificationCodeView.as_view(), name='send-verification-code'),
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('verify-email/', EmailVerificationView.as_view(), name='verify-email'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('delete-user/', UserDeleteView.as_view(), name='delete-user'),
]
# accounts/tests.py
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User


class UserAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_user_registration(self):
        data = {
            "email": "1195560097@qq.com",
            "username": "寒枫",
            "password": "Hzj12345678",
            "confirm_password": "Hzj12345678",
        }
        response = self.client.post('/api/accounts/register/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.count(), 1)

    def test_user_login(self):
        # 先注册用户
        self.test_user_registration()

        # 验证邮箱（手动标记）
        user = User.objects.get(email="1195560097@qq.com")
        user.is_email_verified = True
        user.save()

        # 登录
        data = {
            "email": "1195560097@qq.com",
            "password": "123456",
        }
        response = self.client.post('/api/accounts/login/', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
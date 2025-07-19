from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
import datetime
from django.utils import timezone


class User(AbstractUser):
    # 基本信息
    email = models.EmailField(unique=True)
    phone_regex = RegexValidator(
        regex=r'^1[3-9]\d{9}$',
        message="手机号格式错误，应为11位数字"
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=11,
        blank=True,
        null=False,
        unique=True,
        default=''  # 空字符串作为默认值
    )
    major = models.CharField(max_length=100, blank=True, null=False, default='')  # 空字符串作为默认值
    university = models.CharField(max_length=100, blank=True, null=False, default='汉')  # 空字符串作为默认值

    # 新增年龄字段
    age = models.IntegerField(
        blank=True,
        null=True,
        validators=[
            MinValueValidator(1, message="年龄不能小于1"),
            MaxValueValidator(120, message="年龄不能大于120")
        ]
    )

    # 新增学习阶段字段
    LEARNING_STAGE_CHOICES = [
        ('FRESHMAN_1', '大一上'),
        ('FRESHMAN_2', '大一下'),
        ('SOPHOMORE_1', '大二上'),
        ('SOPHOMORE_2', '大二下'),
        ('JUNIOR_1', '大三上'),
        ('JUNIOR_2', '大三下'),
        ('SENIOR_1', '大四上'),
        ('SENIOR_2', '大四下'),
        ('GRADUATE_STUDENT', '研究生'),
        ('JOB_SEEKER', '应届生'),
        ('EMPLOYED', '社会人士'),
        ('OTHER', '其他'),
    ]
    learning_stage = models.CharField(
        max_length=20,
        choices=LEARNING_STAGE_CHOICES,
        blank=True,
        null=True
    )

    # 个人信息
    name = models.CharField(max_length=40, blank=True, null=False, default='')  # 空字符串作为默认值
    GENDER_CHOICES = [
        ('M', '男'),
        ('F', '女'),
        ('O', '其他'),
    ]
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=False, default='O')
    ethnicity = models.CharField(max_length=50, blank=True, null=True)

    # 地址信息
    province = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    district = models.CharField(max_length=50, blank=True, null=True)
    address = models.CharField(max_length=200, blank=True, null=True)

    # 邮箱验证
    is_email_verified = models.BooleanField(default=True)

    # 使用 email 作为认证字段
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # 创建超级用户时需要的额外字段

    def __str__(self):
        return self.email


class EmailVerificationCode(models.Model):
    email = models.EmailField(unique=True)
    code = models.CharField(max_length=6)  # 6位数字验证码
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=timezone.now)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()

    def save(self, *args, **kwargs):
        # 设置默认过期时间（5分钟后）
        if not self.expires_at:
            self.expires_at = datetime.datetime.now() + datetime.timedelta(minutes=5)
        super().save(*args, **kwargs)    
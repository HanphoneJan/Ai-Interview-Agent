"""
URL configuration for AiInterviewAgent project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path("admin/", admin.site.urls),
    path('api/user/', include('user_manager.urls')),
    # 面试场景管理
    path('api/interview/', include('interview_manager.urls')),
    # 多模态数据管理
    path('api/media/', include('client_media_manager.urls')),
    # 评估系统
    path('api/evaluation/', include('evaluation_system.urls')),
    # 反馈报告
    path('api/feedback/', include('feedback_report.urls')),
]

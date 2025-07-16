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
    path('api/evaluation/', include('evaluation_system.urls'))
]

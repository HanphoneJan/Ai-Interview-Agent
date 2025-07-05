# client_media_manager/views.py
from rest_framework import viewsets, permissions
from .models import ResponseMetadata
from .serializers import ResponseMetadataSerializer

class ResponseMetadataViewSet(viewsets.ModelViewSet):
    """多模态响应元数据管理API"""
    queryset = ResponseMetadata.objects.all()
    serializer_class = ResponseMetadataSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # 自动关联当前用户
        serializer.save(user=self.request.user)

    def get_queryset(self):
        """仅返回当前用户的响应元数据"""
        return self.queryset.filter(question__session__user=self.request.user)
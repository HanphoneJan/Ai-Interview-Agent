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
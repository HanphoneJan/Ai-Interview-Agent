# multimodal_data/serializers.py
from rest_framework import serializers
from .models import ResponseMetadata
from interview_scenarios.models import InterviewQuestion

class ResponseMetadataSerializer(serializers.ModelSerializer):
    question = serializers.PrimaryKeyRelatedField(
        queryset=InterviewQuestion.objects.all()
    )
    total_duration = serializers.SerializerMethodField()

    class Meta:
        model = ResponseMetadata
        fields = [
            'id', 'question', 'audio_duration',
            'video_duration', 'upload_timestamp', 'total_duration'
        ]

    def get_total_duration(self, obj):
        return obj.get_total_duration()
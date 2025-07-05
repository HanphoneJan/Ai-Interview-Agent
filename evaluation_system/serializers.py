# evaluation_system/serializers.py
from rest_framework import serializers
from .models import ResponseAnalysis, AnswerEvaluation, OverallInterviewEvaluation
from client_media_manager.models import ResponseMetadata
from interview_manager.models import InterviewQuestion, InterviewSession
from user_manager.models import User

class ResponseAnalysisSerializer(serializers.ModelSerializer):
    metadata = serializers.PrimaryKeyRelatedField(
        queryset=ResponseMetadata.objects.all()
    )

    class Meta:
        model = ResponseAnalysis
        fields = '__all__'

class AnswerEvaluationSerializer(serializers.ModelSerializer):
    question = serializers.PrimaryKeyRelatedField(
        queryset=InterviewQuestion.objects.all()
    )
    analysis = serializers.PrimaryKeyRelatedField(
        queryset=ResponseAnalysis.objects.all()
    )
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all()
    )

    class Meta:
        model = AnswerEvaluation
        fields = '__all__'

class OverallInterviewEvaluationSerializer(serializers.ModelSerializer):
    session = serializers.PrimaryKeyRelatedField(
        queryset=InterviewSession.objects.all()
    )
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all()
    )

    class Meta:
        model = OverallInterviewEvaluation
        fields = '__all__'

    def validate(self, data):
        # 确保各项能力评分在1-10分之间
        for field in ['professional_knowledge', 'skill_match', 'language_expression', 'logical_thinking', 'innovation', 'stress_response']:
            value = data.get(field)
            if value is not None and (value < 1 or value > 10):
                raise serializers.ValidationError({field: '评分必须在1-10分之间'})
        return data
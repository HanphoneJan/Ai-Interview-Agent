# evaluation_system/tests.py
from django.test import TestCase
from .models import ResponseAnalysis, AnswerEvaluation, OverallInterviewEvaluation
from interview_scenarios.models import InterviewQuestion, InterviewSession, InterviewScenario
from accounts.models import User
from multimodal_data.models import ResponseMetadata

class EvaluationSystemTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.scenario = InterviewScenario.objects.create(name='测试场景', technology_field='测试领域', description='测试描述')
        self.session = InterviewSession.objects.create(user=self.user, scenario=self.scenario)
        self.question = InterviewQuestion.objects.create(session=self.session, question_text='测试问题', question_number=1)
        self.metadata = ResponseMetadata.objects.create(question=self.question)

    def test_response_analysis_creation(self):
        analysis = ResponseAnalysis.objects.create(metadata=self.metadata, speech_text='测试语音文本', facial_expression='测试表情', body_language='测试肢体语言')
        self.assertEqual(analysis.metadata, self.metadata)

    def test_answer_evaluation_creation(self):
        analysis = ResponseAnalysis.objects.create(metadata=self.metadata, speech_text='测试语音文本', facial_expression='测试表情', body_language='测试肢体语言')
        evaluation = AnswerEvaluation.objects.create(question=self.question, analysis=analysis, evaluation_text='测试评估文本', score=5)
        self.assertEqual(evaluation.question, self.question)
        self.assertEqual(evaluation.analysis, analysis)

    def test_overall_interview_evaluation_creation(self):
        evaluation = OverallInterviewEvaluation.objects.create(session=self.session, user=self.user, overall_evaluation='测试整体评估文本', professional_knowledge=5, skill_match=5, language_expression=5, logical_thinking=5, innovation=5, stress_response=5)
        self.assertEqual(evaluation.session, self.session)
        self.assertEqual(evaluation.user, self.user)
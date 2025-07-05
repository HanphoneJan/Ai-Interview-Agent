# client_media_manager/tests.py
from django.test import TestCase
from .models import ResponseMetadata, LiveStreamChunk
from interview_manager.models import InterviewQuestion, InterviewSession, InterviewScenario
from user_manager.models import User

class MultimodalDataTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.scenario = InterviewScenario.objects.create(name='测试场景', technology_field='测试领域', description='测试描述')
        self.session = InterviewSession.objects.create(user=self.user, scenario=self.scenario)
        self.question = InterviewQuestion.objects.create(session=self.session, question_text='测试问题', question_number=1)

    def test_response_metadata_creation(self):
        metadata = ResponseMetadata.objects.create(question=self.question, audio_duration='0:01:00', video_duration='0:02:00')
        self.assertEqual(metadata.question, self.question)
        self.assertEqual(metadata.get_total_duration(), '0:03:00')

    def test_live_stream_chunk_creation(self):
        chunk = LiveStreamChunk.objects.create(session_id='test_session', media_type='audio', chunk_data=b'test_chunk')
        self.assertEqual(chunk.session_id, 'test_session')
        self.assertEqual(chunk.media_type, 'audio')
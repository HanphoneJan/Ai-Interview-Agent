# interview_manager/utils.py
from .models import InterviewSession, InterviewQuestion

def get_current_question(session_id):
    session = InterviewSession.objects.get(id=session_id)
    question_count = InterviewQuestion.objects.filter(session=session).count()
    if question_count > 0:
        return InterviewQuestion.objects.filter(session=session).order_by('-question_number').first()
    return None
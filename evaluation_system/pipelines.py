# evaluation_system/pipelines.py
from .audio_engines import analyze_live_audio, analyze_facial_expression
import logging

logger = logging.getLogger(__name__)

async def live_evaluation_pipeline(session_id, media_chunk, media_type):
    """实时评估流水线（整合多模态分析）"""
    results = {}

    if media_type == "audio":
        results["audio"] = await analyze_live_audio(session_id, media_chunk)
    elif media_type == "video":
        results["video"] = await analyze_facial_expression(media_chunk)
    else:
        logger.warning(f"不支持的媒体类型: {media_type}")

    # 整合分析结果，生成实时反馈
    feedback = generate_live_feedback(results)
    return feedback

def generate_live_feedback(results):
    feedback = {}
    audio_result = results.get("audio")
    video_result = results.get("video")

    if audio_result:
        feedback["audio_feedback"] = f"语音内容: {audio_result['text']}, 置信度: {audio_result['confidence']}"
    if video_result:
        feedback["video_feedback"] = "视频分析结果"  # 根据实际分析结果填充
    return feedback
# evaluation_system/pipelines.py
from .ai_engines import analyze_live_audio, analyze_facial_expression


async def live_evaluation_pipeline(session_id, media_chunk, media_type):
    """实时评估流水线（整合多模态分析）"""
    results = {}

    if media_type == "audio":
        results["audio"] = await analyze_live_audio(session_id, media_chunk)
    elif media_type == "video":
        results["video"] = await analyze_facial_expression(media_chunk)

    # 整合分析结果，生成实时反馈
    feedback = generate_live_feedback(results)
    return feedback
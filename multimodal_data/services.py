# multimodal_data/services.py
import asyncio
from .models import LiveStreamChunk


async def process_live_stream(session_id, chunk, media_type):
    """处理实时媒体流数据（存储或分析）"""
    # 存储媒体块（用于回放或进一步分析）
    LiveStreamChunk.objects.create(
        session_id=session_id,
        media_type=media_type,
        chunk_data=chunk
    )

    # 异步触发AI分析（语音转文字、表情识别等）
    asyncio.create_task(trigger_ai_analysis(session_id, chunk, media_type))
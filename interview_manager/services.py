# interview_manager/services.py
import logging
from evaluation_system.models import LiveStreamChunk
from evaluation_system.audio_recognize_engine import recognize
from evaluation_system.facial_engine import FacialExpressionAnalyzer
import asyncio

logger = logging.getLogger(__name__)

async def process_live_stream(session_id, chunk, media_type):
    """处理实时媒体流数据（存储或分析）"""
    try:
        # 存储媒体块（用于回放或进一步分析）
        LiveStreamChunk.objects.create(
            session_id=session_id,
            media_type=media_type,
            chunk_data=chunk
        )
        logger.info(f"成功存储 {media_type} 数据块，会话ID: {session_id}")

        # 异步触发AI分析（语音转文字、表情识别等）
        asyncio.create_task(trigger_ai_analysis(session_id, chunk, media_type))
    except Exception as e:
        logger.error(f"处理实时媒体流数据出错: {e}")

async def trigger_ai_analysis(session_id, chunk, media_type):
    """触发AI分析任务"""
    if media_type == "audio":
        # 语音识别
        result = await recognize(chunk)
        if result["success"]:
            logger.info(f"语音识别结果: {result['text']}")
    elif media_type == "video":
        # 表情分析
        analyzer = FacialExpressionAnalyzer()
        try:
            # 假设视频数据是二进制数据，保存为临时文件进行分析
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                f.write(chunk)
                temp_img_path = f.name
            # 调用 analyze_by_file 方法
            analysis_result = await asyncio.to_thread(analyzer.analyze_by_file, file_path=temp_img_path)
            # 删除临时文件
            os.unlink(temp_img_path)
            if analysis_result["success"]:
                logger.info(f"视频表情分析结果: {analysis_result['data']}")
        except Exception as e:
            logger.error(f"视频分析出错: {e}")
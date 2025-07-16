# evaluation_system/pipelines.py
from .audio_recognize_engine import recognize
from .facial_engine import FacialExpressionAnalyzer
import logging
import asyncio
import tempfile
import os

logger = logging.getLogger(__name__)

async def live_evaluation_pipeline(session_id, media_chunk, media_type):
    results = {}
    analyzer = FacialExpressionAnalyzer()

    if media_type == "audio":
        # 修正调用，原代码多传了 session_id
        results["audio"] = await recognize(media_chunk)
    elif media_type == "video":
        try:
            # 假设视频数据是二进制数据，保存为临时文件进行分析
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                f.write(media_chunk)
                temp_img_path = f.name
            # 调用 analyze_by_file 方法
            results["video"] = await asyncio.to_thread(analyzer.analyze_by_file, file_path=temp_img_path)
            # 删除临时文件
            os.unlink(temp_img_path)
        except Exception as e:
            logger.error(f"视频分析出错: {e}")
    else:
        logger.warning(f"不支持的媒体类型: {media_type}")

    # 整合分析结果，生成实时反馈
    feedback = generate_live_feedback(results)

    # 调用答案评估模块
    if results.get("audio"):
        speech_text = results["audio"]["text"]
        # 假设我们可以通过 session_id 获取当前问题
        # question = get_current_question(session_id)
        # 创建响应分析记录
        # response_analysis = ResponseAnalysis.objects.create(
        #     metadata=metadata,
        #     speech_text=speech_text,
        #     facial_expression=results.get("video", {}).get("expression", ""),
        #     body_language=""
        # )
        # 创建答案评估记录
        # answer_evaluation = AnswerEvaluation.objects.create(
        #     question=question,
        #     analysis=response_analysis,
        #     evaluation_text="",
        #     score=0
        # )

    return feedback

def generate_live_feedback(results):
    feedback = {}
    audio_result = results.get("audio")
    video_result = results.get("video")

    if audio_result:
        # 处理可能不存在的 confidence 字段
        confidence = audio_result.get('confidence', '未知')
        feedback["audio_feedback"] = f"语音内容: {audio_result['text']}, 置信度: {confidence}"
    if video_result and video_result["success"]:
        feedback["video_feedback"] = f"视频分析结果: {video_result['data']}"
    return feedback
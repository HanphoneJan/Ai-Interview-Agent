# interview_manager/services.py
import logging
import base64
import cv2
import tempfile
import os
import asyncio
import subprocess
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from asgiref.sync import sync_to_async
from .models import InterviewSession, InterviewQuestion
from evaluation_system.models import   LiveStreamChunk, ResponseMetadata, ResponseAnalysis, AnswerEvaluation
from evaluation_system.audio_recognize_engine import recognize
from evaluation_system.facial_engine import FacialExpressionAnalyzer
from evaluation_system.evaluate_engine import spark_ai_engine
from evaluation_system.audio_generate_engine import synthesize
from interview_manager.utils import send_audio_to_client

logger = logging.getLogger(__name__)


async def process_live_media(session_id, base64_data, timestamp, user_id):
    """处理前端发送的实时媒体数据"""
    try:
        # 解码base64数据
        webm_bytes = base64.b64decode(base64_data)

        # 存储原始媒体块
        chunk = await sync_to_async(_save_media_chunk)(
            session_id, webm_bytes, timestamp, user_id
        )

        # 异步处理媒体数据
        asyncio.create_task(_analyze_media_chunk(chunk))

        return {"success": True, "message": "媒体数据接收成功"}

    except Exception as e:
        logger.error(f"处理媒体数据失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


# 确保这是一个同步函数
def _save_media_chunk(session_id, data, timestamp, user_id):
    """保存媒体块到数据库和文件系统"""
    session = InterviewSession.objects.get(id=session_id)

    # 保存文件到Django存储
    file_name = f"interview_{session_id}_{timestamp}.webm"
    file_path = default_storage.save(f"media_chunks/{file_name}", ContentFile(data))

    # 创建数据库记录
    return LiveStreamChunk.objects.create(
        session=session,
        file=file_path,
        timestamp=timestamp,
        user_id=user_id,
        file_size=len(data)
    )


async def _analyze_media_chunk(chunk):
    """分析媒体块（音频+视频）"""
    try:
        # 从存储中读取文件内容
        with default_storage.open(chunk.file.name, 'rb') as f:
            media_bytes = f.read()

        # 并行处理音频和视频
        audio_task = asyncio.create_task(_process_audio(chunk.session, media_bytes, chunk.timestamp))
        video_task = asyncio.create_task(_process_video(chunk.session, media_bytes, chunk.timestamp))

        await asyncio.gather(audio_task, video_task)

        # 标记为已处理
        chunk.processed = True
        await sync_to_async(chunk.save)()

    except Exception as e:
        logger.error(f"分析媒体块失败: {str(e)}", exc_info=True)
        # 可以添加重试逻辑或标记为处理失败


async def _process_audio(session, media_bytes, timestamp):
    """处理音频数据"""
    audio_bytes = await _extract_audio_from_webm(media_bytes)
    if not audio_bytes:
        logger.error("提取音频失败")
        return

    # 语音识别
    result = await recognize(audio_bytes)
    if not result["success"]:
        logger.error(f"语音识别失败: {result.get('error', '未知错误')}")
        return

    speech_text = result["text"]
    logger.info(f"语音识别结果: {speech_text[:50]}...")

    # 保存识别结果
    current_question = await sync_to_async(
        InterviewQuestion.objects.filter(session=session).latest
    )('asked_at')

    metadata = await sync_to_async(ResponseMetadata.objects.create)(
        question=current_question,
        audio_duration=len(audio_bytes) / (16000 * 2)  # 估算秒数 (采样率*位深)
    )

    analysis = await sync_to_async(ResponseAnalysis.objects.create)(
        metadata=metadata,
        speech_text=speech_text,
        timestamp=timestamp
    )

    # 评估回答并生成新问题
    await evaluate_and_generate_question(session, speech_text, analysis)


async def _process_video(session, media_bytes, timestamp):
    """处理视频数据"""
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
            temp_path = f.name
            f.write(media_bytes)

        # 验证文件是否为有效的WebM格式
        if not _is_valid_webm(temp_path):
            raise Exception("文件不是有效的WebM格式")

        # 转换为MP4以提高兼容性
        mp4_path = tempfile.mktemp(suffix='.mp4')
        await _convert_to_mp4(temp_path, mp4_path)

        # 分析视频帧
        analysis = await _analyze_video_frames(mp4_path)

        # 清理临时文件
        os.unlink(temp_path)
        os.unlink(mp4_path)

        # 保存分析结果
        if analysis and analysis.get("success"):
            # 这里可以将分析结果与相关模型关联
            logger.info(f"视频分析完成，共{len(analysis['data'])}帧")

            # 更新最近的ResponseAnalysis记录
            latest_analysis = await sync_to_async(
                ResponseAnalysis.objects.filter(metadata__question__session=session)
                .order_by('-timestamp').first
            )()

            if latest_analysis:
                latest_analysis.facial_expression = str(analysis['data'])
                await sync_to_async(latest_analysis.save)()

    except Exception as e:
        logger.error(f"视频处理失败: {str(e)}", exc_info=True)


async def _analyze_video_frames(video_path):
    """分析视频帧获取表情和肢体语言"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"success": False, "error": "无法打开视频文件"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_interval = int(fps)  # 每秒分析一帧
    frame_count = 0
    results = []

    facial_analyzer = FacialExpressionAnalyzer()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_interval == 0:
            # 异步分析帧
            frame_result = await asyncio.to_thread(
                facial_analyzer.analyze_frame, frame
            )
            results.append({
                "frame": frame_count,
                "timestamp": frame_count / fps,
                "analysis": frame_result
            })

        frame_count += 1

    cap.release()
    return {"success": True, "data": results}


# 从webm中提取音频（用于语音识别）
async def _extract_audio_from_webm(webm_bytes):
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
            webm_path = f.name
            f.write(webm_bytes)

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            audio_path = f.name

        # 执行FFmpeg命令
        cmd = [
            'ffmpeg', '-i', webm_path,
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1', '-y', audio_path
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            # 记录详细的FFmpeg错误信息
            logger.error(f"FFmpeg命令: {' '.join(cmd)}")
            logger.error(f"FFmpeg错误输出: {stderr.decode()}")
            raise Exception(f"FFmpeg提取音频失败: {stderr.decode()}")

        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()

        return audio_bytes

    except Exception as e:
        logger.error(f"提取音频失败: {str(e)}", exc_info=True)
        return None
    finally:
        # 清理临时文件
        for path in [webm_path, audio_path] if 'webm_path' in locals() else []:
            if os.path.exists(path):
                os.unlink(path)


# 验证文件是否为有效的WebM格式
def _is_valid_webm(file_path):
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
            # WebM文件以4字节的"webm"标识开头
            return header == b'\x1A\x45\xDF\xA3'
    except Exception:
        return False


# 使用FFmpeg将WebM转换为MP4
async def _convert_to_mp4(input_path, output_path):
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-c:v', 'libx264',  # 使用H.264编码
        '-crf', '23',  # 视频质量（0-51，越低质量越高）
        '-preset', 'medium',  # 编码速度与压缩比的平衡
        '-y',  # 覆盖已存在文件
        output_path
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise Exception(f"FFmpeg转换失败: {stderr.decode()}")


# 评估回答并生成新问题
async def evaluate_and_generate_question(session, speech_text, analysis):
    evaluation_response = spark_ai_engine.generate_response(
        f"评估面试回答: {speech_text}", []  # 这里应该传递对话历史
    )
    if evaluation_response["success"]:
        evaluation_text = evaluation_response["content"]
        current_question = await sync_to_async(
            InterviewQuestion.objects.filter(session=session).latest
        )('asked_at')
        await sync_to_async(AnswerEvaluation.objects.create)(
            question=current_question,
            analysis=analysis,
            evaluation_text=evaluation_text,
            score=0  # 可根据实际逻辑调整评分
        )

        # 生成新问题
        new_question_response = spark_ai_engine.generate_response(
            "生成下一个面试问题", []  # 这里应该传递对话历史
        )
        if new_question_response["success"]:
            new_question_text = new_question_response["content"]

            question_count = await sync_to_async(
                InterviewQuestion.objects.filter(session=session).count
            )()
            await sync_to_async(InterviewQuestion.objects.create)(
                session=session,
                question_text=new_question_text,
                question_number=question_count + 1
            )

            # 生成语音
            audio_result = await synthesize(new_question_text)
            if audio_result["success"]:
                await send_audio_to_client(session.id, audio_result["audio_data"])
        else:
            logger.error("生成新问题失败")
    else:
        logger.error("评估回答失败")
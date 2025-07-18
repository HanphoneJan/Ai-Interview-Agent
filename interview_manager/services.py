import logging
import base64
import cv2
import os
import subprocess
import sys  # 新增：用于判断操作系统
from django.conf import settings
import asyncio
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from asgiref.sync import sync_to_async
from .models import InterviewSession, InterviewQuestion
from evaluation_system.models import ResponseMetadata, ResponseAnalysis, AnswerEvaluation
from evaluation_system.audio_recognize_engine import recognize
from evaluation_system.facial_engine import FacialExpressionAnalyzer
from evaluation_system.evaluate_engine import spark_ai_engine
from evaluation_system.audio_generate_engine import synthesize
from interview_manager.utils import send_audio_and_text_to_client  # 修改导入的函数名
import platform
import time  # 新增：用于记录时间

logger = logging.getLogger(__name__)

CUSTOM_TEMP_DIR = os.path.join(settings.MEDIA_ROOT, 'custom_temp')
# 确保自定义临时目录存在，不存在则创建
os.makedirs(CUSTOM_TEMP_DIR, exist_ok=True)
# 新增：Windows 系统事件循环初始化（程序启动时执行一次）
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        logger.info("已为Windows系统设置ProactorEventLoop")
    except AttributeError:
        logger.warning("当前Python版本不支持WindowsProactorEventLoopPolicy，可能存在兼容性问题")


async def process_live_media(session_id, base64_data, timestamp, user_id):
    """处理前端发送的实时媒体数据"""
    try:
        # 解码base64数据
        webm_bytes = base64.b64decode(base64_data)

        # 仅保存到文件系统，不创建数据库记录
        file_path = await sync_to_async(_save_media_to_filesystem)(
            session_id, webm_bytes, timestamp
        )

        # 异步处理媒体数据，传递文件路径而非数据库对象
        asyncio.create_task(_analyze_media_file(session_id, file_path, timestamp, user_id))

        return {"success": True, "message": "媒体数据接收成功"}

    except Exception as e:
        logger.error(f"处理媒体数据失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


def _save_media_to_filesystem(session_id, data, timestamp):
    """仅保存媒体块到文件系统，不涉及数据库"""
    file_name = f"interview_{session_id}_{timestamp}.webm"
    file_path = default_storage.save(f"media_chunks/{file_name}", ContentFile(data, name=file_name))
    return file_path


async def _analyze_media_file(session_id, file_path, timestamp, user_id):
    """分析媒体文件（音频+视频），不依赖数据库记录"""
    try:
        session = await sync_to_async(InterviewSession.objects.get)(id=session_id)

        # 从存储中读取文件内容
        with default_storage.open(file_path, 'rb') as f:
            media_bytes = f.read()

        # 并行处理音频和视频
        audio_task = asyncio.create_task(_process_audio(session, media_bytes, timestamp))
        video_task = asyncio.create_task(_process_video(session, media_bytes, timestamp))

        await asyncio.gather(audio_task, video_task)

        # 分析完成后可选择删除原始文件（根据需求决定）
        # await sync_to_async(default_storage.delete)(file_path)

    except Exception as e:
        logger.error(f"分析媒体文件失败: {str(e)}", exc_info=True)


async def _process_audio(session, media_bytes, timestamp):
    """处理音频数据（仅存储识别后的文本和元数据）"""
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    audio_bytes = await _extract_audio_from_webm(media_bytes)
    if not audio_bytes:
        logger.error("提取音频失败")
        return

    # 语音识别（将音频转为文本）
    result = await recognize(audio_bytes)
    if not result["success"]:
        logger.error(f"语音识别失败: {result.get('error', '未知错误')}")
        return

    speech_text = result["text"]
    logger.info(f"语音识别结果: {speech_text[:50]}...")

    # 保存识别结果（均为文本/数值元数据）
    current_question = await sync_to_async(
        InterviewQuestion.objects.filter(session=session).latest
    )('asked_at')

    metadata = await sync_to_async(ResponseMetadata.objects.create)(
        question=current_question,
        audio_duration=len(audio_bytes) / (16000 * 2)  # 估算秒数 (采样率*位深)
    )

    analysis = await sync_to_async(ResponseAnalysis.objects.create)(
        metadata=metadata,
        speech_text=speech_text,  # 文本数据
        timestamp=timestamp
    )

    # 评估回答并生成新问题
    await evaluate_and_generate_question(session, speech_text, analysis)


async def _process_video(session, media_bytes, timestamp):
    """处理视频（修复临时文件删除逻辑）"""
    temp_path = None
    mp4_path = None
    try:
        # 生成自定义目录下的 webm 临时文件
        webm_filename = f"interview_{session.id}_{timestamp}_temp.webm"
        temp_path = os.path.join(CUSTOM_TEMP_DIR, webm_filename)
        with open(temp_path, 'wb') as f:
            f.write(media_bytes)

        if not _is_valid_webm(temp_path):
            raise Exception("文件不是有效的WebM格式")

        # 生成自定义目录下的 mp4 临时文件
        mp4_filename = f"interview_{session.id}_{timestamp}_temp.mp4"
        mp4_path = os.path.join(CUSTOM_TEMP_DIR, mp4_filename)
        await _convert_to_mp4(temp_path, mp4_path)

        analysis = await _analyze_video_frames(mp4_path)
        logger.info(f"视频分析完成，共{len(analysis['data'])}帧")

        latest_analysis = await sync_to_async(
            ResponseAnalysis.objects.filter(metadata__question__session=session)
            .order_by('-analysis_timestamp').first  # 改为使用 analysis_timestamp
        )()

        if latest_analysis:
            latest_analysis.facial_expression = str(analysis['data'])
            await sync_to_async(latest_analysis.save)()

    except Exception as e:
        logger.error(f"视频处理失败: {str(e)}", exc_info=True)
    finally:
        # 确保临时文件删除（先检查存在性）
        for path in [temp_path, mp4_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.info(f"删除临时文件: {path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {path}, 错误: {str(e)}")


async def _analyze_video_frames(video_path):
    """分析视频帧获取表情和肢体语言（返回文本化的分析结果）"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"success": False, "error": "无法打开视频文件"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_count = 0
    results = []  # 存储文本化的表情分析结果
    facial_analyzer = FacialExpressionAnalyzer()
    last_analysis_time = time.time()  # 记录上次分析的时间

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        current_time = time.time()
        # 只有当距离上次分析时间超过60秒时才进行分析
        if (current_time - last_analysis_time) >= 60:
            # 异步分析帧（获取表情等文本化特征）
            frame_result = await asyncio.to_thread(
                facial_analyzer.analyze_frame, frame
            )
            # frame_result应为字典形式的文本化结果（如{'expression': 'smile', 'confidence': 0.8}）
            results.append({
                "frame": frame_count,
                "timestamp": frame_count / fps,
                "analysis": frame_result  # 已文本化的分析结果
            })
            last_analysis_time = current_time  # 更新上次分析的时间

        frame_count += 1

    cap.release()
    return {"success": True, "data": results}


async def _check_ffmpeg_available():
    """检查FFmpeg是否可执行（兼容Windows系统）"""
    try:
        # 对Windows系统进行特殊处理
        if sys.platform == 'win32':
            # 使用cmd.exe来执行命令（Windows兼容方式）
            proc = await asyncio.create_subprocess_exec(
                'cmd.exe', '/c', 'ffmpeg', '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:
            # 非Windows系统直接执行
            proc = await asyncio.create_subprocess_exec(
                'ffmpeg', '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

        await proc.communicate()
        return proc.returncode == 0

    except FileNotFoundError:
        return False
    except NotImplementedError:
        # 当asyncio方法失败时，使用同步subprocess作为备选方案
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

async def has_audio_stream(file_path):
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'a',
            '-show_entries', 'stream=codec_type',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return 'audio' in result.stdout
    except Exception as e:
        print(f"检查音频流时出错: {e}")
        return False


async def _extract_audio_from_webm(webm_bytes):
    """提取音频（使用自定义临时目录）"""
    if not await _check_ffmpeg_available():
        logger.error("FFmpeg未安装或不在系统PATH中，请先安装FFmpeg")
        return None

    webm_path = None
    audio_path = None
    try:
        # 生成自定义目录下的 webm 临时文件
        webm_filename = f"audio_extract_{os.urandom(8).hex()}_temp.webm"
        webm_path = os.path.join(CUSTOM_TEMP_DIR, webm_filename)
        with open(webm_path, 'wb') as f:
            f.write(webm_bytes)
        logger.info(f"创建自定义临时WebM文件: {webm_path}")

        # 验证文件是否有效
        if not _is_valid_webm(webm_path):
            logger.error("无效的WebM文件格式")
            return None
        if not await has_audio_stream(webm_path):
            logger.error("输入的WebM文件不包含音频流")
            return None
        # 生成自定义目录下的 wav 临时文件
        wav_filename = f"audio_extract_{os.urandom(8).hex()}_temp.wav"
        audio_path = os.path.join(CUSTOM_TEMP_DIR, wav_filename)
        logger.info(f"创建自定义临时WAV文件: {audio_path}")

        # 构建FFmpeg命令 - 添加更详细的日志记录
        cmd = [
            'ffmpeg',
            '-hide_banner',  # 隐藏横幅信息
            '-loglevel', 'error',  # 只显示错误信息
            '-i', webm_path,
            '-vn',  # 禁用视频
            '-acodec', 'pcm_s16le',
            '-ar', '16000',  # 采样率16kHz
            '-ac', '1',  # 单声道
            '-y',  # 覆盖输出文件
            audio_path
        ]
        logger.info(f"执行FFmpeg命令: {' '.join(cmd)}")

        def run_sync():
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',
                check=False  # 不自动抛出异常，我们自己处理
            )

        # 在异步环境中运行同步subprocess
        proc = await asyncio.to_thread(run_sync)

        if proc.returncode != 0:
            error_msg = f"FFmpeg错误 (返回码: {proc.returncode}): {proc.stderr}"
            logger.error(error_msg)

            # 检查常见错误
            if "Invalid data found when processing input" in proc.stderr:
                logger.error("输入文件格式无效或损坏")
            elif "Permission denied" in proc.stderr:
                logger.error("文件访问权限问题")
            elif "No such file or directory" in proc.stderr:
                logger.error("文件路径不存在")

            raise Exception(error_msg)

        # 验证输出文件是否存在且非空
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            logger.error("输出WAV文件创建失败或为空")
            return None

        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()

        if not audio_bytes:
            logger.error("读取的音频数据为空")
            return None

        return audio_bytes

    except Exception as e:
        logger.error(f"提取音频失败: {str(e)}", exc_info=True)
        return None
    finally:
        # 清理临时文件（先检查文件是否存在）
        for path in [webm_path, audio_path] if 'webm_path' in locals() else []:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.info(f"删除临时文件: {path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {path}, 错误: {str(e)}")


async def _convert_to_mp4(input_path, output_path):
    """转换视频（添加文件存在检查）"""
    if not await _check_ffmpeg_available():
        logger.error("FFmpeg未安装或不在系统PATH中，请先安装FFmpeg")
        raise Exception("FFmpeg不可用")

    try:
        # 构建转换命令
        cmd = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264', '-crf', '23',
            '-preset', 'medium', '-y', output_path
        ]
        logger.info(f"执行FFmpeg转换命令: {' '.join(cmd)}")

        # Windows平台使用同步subprocess
        if sys.platform == 'win32':
            def run_sync():
                return subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )

            # 在异步环境中运行同步subprocess
            proc = await asyncio.to_thread(run_sync)
            if proc.returncode != 0:
                logger.error(f"FFmpeg转换错误: {proc.stderr.decode('utf-8', errors='replace')}")
                raise Exception(f"FFmpeg转换失败，返回码: {proc.returncode}")
        else:
            # 非Windows平台继续使用异步subprocess
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"FFmpeg转换错误: {stderr.decode('utf-8', errors='replace')}")
                raise Exception(f"FFmpeg转换失败，返回码: {proc.returncode}")

    except Exception as e:
        logger.error(f"转换视频失败: {str(e)}", exc_info=True)
        raise


def _is_valid_webm(file_path):
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
            return header == b'\x1A\x45\xDF\xA3'
    except Exception:
        return False

async def generate_initial_question(session):
    new_question_response = spark_ai_engine.generate_response(
        "生成初始面试问题", []
    )
    if new_question_response["success"]:
        new_question_text = new_question_response["content"]
        await sync_to_async(InterviewQuestion.objects.create)(
            session=session,
            question_text=new_question_text,
            question_number=1
        )

        audio_result = await synthesize(new_question_text)
        if audio_result["success"]:
            # 确保audio_data是bytes类型
            audio_data = audio_result["audio_data"]
            if isinstance(audio_data, str):
                # 如果已经是base64字符串，解码为bytes
                audio_data = base64.b64decode(audio_data)
            await send_audio_and_text_to_client(
                session.id,
                audio_data,  # 发送bytes数据
                new_question_text
            )

async def evaluate_and_generate_question(session, speech_text, analysis):
    evaluation_response = spark_ai_engine.generate_response(
        f"评估面试回答: {speech_text}", []
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
            score=0
        )

        # 生成新问题
        new_question_response = spark_ai_engine.generate_response(
            "生成下一个面试问题", []
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

            # 生成语音（音频数据仅用于传输，不存入数据库）
            audio_result = await synthesize(new_question_text)
            if audio_result["success"]:
                await send_audio_and_text_to_client(session.id, audio_result["audio_data"], new_question_text)  # 修改调用的函数名
        else:
            logger.error("生成新问题失败")
    else:
        logger.error("评估回答失败")
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


async def process_live_media(session_id, base64_data, timestamp, user_id, media_type):
    """处理前端发送的实时媒体数据"""
    try:
        # 解码base64数据
        webm_bytes = base64.b64decode(base64_data)

        # 保存到文件系统
        file_path = await sync_to_async(_save_media_to_filesystem)(
            session_id, webm_bytes, timestamp,media_type
        )

        # 根据媒体类型选择处理方式
        if media_type == "audio":
            asyncio.create_task(_process_audio(session_id, file_path, timestamp))
        elif media_type == "video":
            asyncio.create_task(_process_video(session_id, file_path, timestamp))

        return {"success": True, "message": f"{media_type}数据接收成功"}

    except Exception as e:
        logger.error(f"处理{media_type}数据失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


def _save_media_to_filesystem(session_id, data, timestamp, media_type):
    """仅保存媒体块到文件系统，不涉及数据库"""
    file_name = f"interview_{session_id}_{timestamp}_{media_type}.webm"
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
        logger.error("语音识别：无音频数据可提取")
        return

    # 语音识别（将音频转为文本）
    result = await recognize(audio_bytes)
    if not result["success"]:
        logger.error(f"语音识别失败: {result.get('error', '未知错误')}")
        return

    speech_text = result["text"]
    logger.info(f"语音识别结果: {speech_text[:50]}...")

    # 计算音频时长（秒）并转换为PostgreSQL interval格式
    duration_seconds = len(audio_bytes) / (16000 * 2)  # 估算秒数 (采样率*位深)
    duration_interval = f"{duration_seconds} seconds"  # PostgreSQL interval格式

    # 保存识别结果
    current_question = await sync_to_async(
        InterviewQuestion.objects.filter(session=session).latest
    )('asked_at')

    metadata = await sync_to_async(ResponseMetadata.objects.create)(
        question=current_question,
        audio_duration=duration_interval  # 使用interval格式
    )

    analysis = await sync_to_async(ResponseAnalysis.objects.create)(
        metadata=metadata,
        speech_text=speech_text,
        timestamp=timestamp
    )

    # 评估回答并生成新问题
    await evaluate_and_generate_question(session, speech_text, analysis)


async def _process_video(session_id, file_path, timestamp):
    """处理视频数据，增强BASE64数据处理"""
    try:
        # 从存储中读取文件内容
        with default_storage.open(file_path, 'rb') as f:
            media_bytes = f.read()

        # 确保数据是字节类型
        if isinstance(media_bytes, str):
            try:
                media_bytes = base64.b64decode(media_bytes)
            except Exception as e:
                logger.error(f"视频数据BASE64解码失败: {str(e)}")
                return

        # 创建临时文件进行分析
        temp_path = os.path.join(CUSTOM_TEMP_DIR, f"video_{timestamp}.webm")
        try:
            with open(temp_path, 'wb') as f:
                f.write(media_bytes)

            # 验证视频文件
            if not _is_valid_webm(temp_path):
                logger.error("处理视频：无效的WebM视频文件")
                return

            # 分析视频帧
            analysis_result = await _analyze_video_frames(temp_path)

            if not analysis_result.get("success"):
                logger.error(f"视频分析失败: {analysis_result.get('error', '未知错误')}")
                return

            frame_data = analysis_result.get("data", [])
            logger.info(f"视频分析完成，共分析{len(frame_data)}帧")

            # 保存分析结果
            session = await sync_to_async(InterviewSession.objects.get)(id=session_id)
            latest_analysis = await sync_to_async(
                ResponseAnalysis.objects.filter(metadata__question__session=session)
                .order_by('-analysis_timestamp').first
            )()

            if latest_analysis:
                valid_data = [d for d in frame_data if d.get("analysis")]
                latest_analysis.facial_expression = str(valid_data)
                await sync_to_async(latest_analysis.save)()
                logger.info("视频分析结果保存成功")

        finally:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"删除临时视频文件失败: {str(e)}")

    except Exception as e:
        logger.error(f"处理视频失败: {str(e)}", exc_info=True)
    finally:
        if file_path and default_storage.exists(file_path):
            await sync_to_async(default_storage.delete)(file_path)


async def _analyze_video_frames(video_bytes):
    """分析视频帧获取表情和肢体语言"""
    temp_path = None
    try:
        # 确保输入数据是字节类型
        if isinstance(video_bytes, str):
            # 如果是base64字符串，解码为字节
            try:
                video_bytes = base64.b64decode(video_bytes)
            except Exception as e:
                logger.error(f"BASE64解码失败: {str(e)}")
                return {"success": False, "error": "无效的视频数据格式", "data": []}

        # 创建临时文件
        temp_path = os.path.join(CUSTOM_TEMP_DIR, f"video_{int(time.time() * 1000)}.webm")
        with open(temp_path, 'wb') as f:  # 注意使用二进制写入模式
            f.write(video_bytes)

        # 验证文件是否有效
        if not _is_valid_webm(temp_path):
            logger.error("提取视频：无效的WebM视频文件")
            return {"success": False, "error": "无效的视频文件格式", "data": []}

        # 使用OpenCV打开视频
        cap = cv2.VideoCapture(temp_path)
        if not cap.isOpened():
            # 尝试用FFmpeg后端打开
            cap = cv2.VideoCapture(temp_path, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                logger.error("无法打开视频文件")
                return {"success": False, "error": "无法打开视频文件", "data": []}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_count = 0
        results = []
        facial_analyzer = FacialExpressionAnalyzer()
        last_analysis_time = time.time()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_time = time.time()
            if (current_time - last_analysis_time) >= 10:  # 每10秒分析一帧
                try:
                    frame_result = await asyncio.to_thread(
                        facial_analyzer.analyze_frame, frame
                    )
                    if frame_result.get("success"):
                        results.append({
                            "frame": frame_count,
                            "timestamp": frame_count / fps,
                            "analysis": frame_result.get("data", {})
                        })
                    last_analysis_time = current_time
                except Exception as e:
                    logger.error(f"分析视频帧失败: {str(e)}")

            frame_count += 1

        cap.release()
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"视频分析失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "data": []}
    finally:
        pass
        # if temp_path and os.path.exists(temp_path):
        #     try:
        #         os.unlink(temp_path)
        #     except Exception as e:
        #         logger.warning(f"删除临时文件失败: {str(e)}")


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


async def _extract_audio_from_webm(webm_data):
    """提取音频（使用自定义临时目录）"""
    if not await _check_ffmpeg_available():
        logger.error("FFmpeg未安装或不在系统PATH中，请先安装FFmpeg")
        return None

    webm_path = None
    audio_path = None
    try:
        # 确保输入数据是字节类型
        if isinstance(webm_data, str):
            # 如果是base64字符串，解码为字节
            webm_bytes = base64.b64decode(webm_data)
        else:
            webm_bytes = webm_data

        # 生成自定义目录下的 webm 临时文件
        webm_filename = f"audio_extract_{os.urandom(8).hex()}_temp.webm"
        webm_path = os.path.join(CUSTOM_TEMP_DIR, webm_filename)

        # 以二进制模式写入文件
        with open(webm_path, 'wb') as f:
            f.write(webm_bytes)

        logger.info(f"创建自定义临时WebM文件: {webm_path}")

        # 验证文件是否有效
        if not _is_valid_webm(webm_path):
            logger.error("提取音频：无效的WebM文件格式")
            return None

        # 检查文件大小
        file_size = os.path.getsize(webm_path)
        if file_size < 1024:  # 小于1KB视为无效
            logger.error(f"文件过小({file_size}字节)，可能不完整")
            return None

        if not await has_audio_stream(webm_path):
            logger.info("输入的WebM文件不包含音频流")
            return None

        # 生成自定义目录下的 mp3 临时文件
        mp3_filename = f"audio_extract_{os.urandom(8).hex()}_temp.mp3"
        audio_path = os.path.join(CUSTOM_TEMP_DIR, mp3_filename)

        # 构建FFmpeg命令
        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-i', webm_path,
            '-vn',
            '-acodec', 'libmp3lame',
            '-q:a', '2',
            '-ar', '16000',
            '-ac', '1',
            '-y',
            audio_path
        ]
        logger.info(f"执行FFmpeg命令: {' '.join(cmd)}")

        # Windows平台使用同步subprocess
        if sys.platform == 'win32':
            def run_sync():
                return subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False
                )

            proc = await asyncio.to_thread(run_sync)
            stdout, stderr = proc.stdout, proc.stderr
            returncode = proc.returncode
        else:
            # 非Windows平台使用异步subprocess
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            returncode = proc.returncode

        if returncode != 0:
            error_msg = f"FFmpeg错误 (返回码: {returncode}): {stderr.decode('utf-8', errors='replace')}"
            logger.error(error_msg)
            raise Exception(error_msg)

        # 验证输出文件
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            logger.error("输出MP3文件创建失败或为空")
            return None

        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()

        return audio_bytes

    except Exception as e:
        logger.error(f"提取音频失败: {str(e)}", exc_info=True)
        return None
    finally:
        pass
        # 清理临时文件
        # for path in [webm_path, audio_path]:
        #     if path and os.path.exists(path):
        #         try:
        #             os.unlink(path)
        #         except Exception as e:
        #             logger.warning(f"删除临时文件失败: {path}, 错误: {str(e)}")


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
    """验证WebM文件有效性"""
    try:
        # 检查文件头
        with open(file_path, 'rb') as f:
            header = f.read(4)
            if header != b'\x1A\x45\xDF\xA3':
                return False

        # 检查文件是否完整
        file_size = os.path.getsize(file_path)
        if file_size < 1024:  # 小于1KB视为无效
            return False

        # 使用FFprobe进行更深入的验证
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_format', file_path]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError:
            return False

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
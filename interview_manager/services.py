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

# 根据媒体类型创建不同的临时目录
CUSTOM_TEMP_DIR = os.path.join(settings.MEDIA_ROOT, 'custom_temp')
AUDIO_TEMP_DIR = os.path.join(CUSTOM_TEMP_DIR, 'audio')
VIDEO_TEMP_DIR = os.path.join(CUSTOM_TEMP_DIR, 'video')

# 确保所有临时目录存在
for dir_path in [CUSTOM_TEMP_DIR, AUDIO_TEMP_DIR, VIDEO_TEMP_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# 新增：Windows 系统事件循环初始化（程序启动时执行一次）
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        logger.info("已为Windows系统设置ProactorEventLoop")
    except AttributeError:
        logger.warning("当前Python版本不支持WindowsProactorEventLoopPolicy，可能存在兼容性问题")


def safe_base64_decode(base64_data):
    """安全的base64解码，处理常见的编码问题"""
    try:
        if not base64_data:
            logger.error("Base64数据为空")
            return None

        if isinstance(base64_data, bytes):
            # 如果已经是bytes类型，直接返回
            return base64_data

        if not isinstance(base64_data, str):
            logger.error(f"Base64数据类型错误: {type(base64_data)}")
            return None

        # 移除可能的数据URL前缀（虽然前端发送纯base64，但作为保险措施）
        if base64_data.startswith('data:'):
            base64_data = base64_data.split(',', 1)[1]

        # 移除可能的空白字符
        base64_data = base64_data.strip()

        # 验证base64字符集
        import string
        valid_chars = set(string.ascii_letters + string.digits + '+/=')
        if not all(c in valid_chars for c in base64_data):
            logger.error("Base64数据包含无效字符")
            return None

        # 确保base64字符串长度是4的倍数
        missing_padding = len(base64_data) % 4
        if missing_padding:
            base64_data += '=' * (4 - missing_padding)

        # 解码
        decoded_data = base64.b64decode(base64_data)

        # 验证解码后数据不为空
        if not decoded_data:
            logger.error("Base64解码后数据为空")
            return None

        return decoded_data

    except Exception as e:
        logger.error(f"Base64解码失败: {str(e)}")
        return None


def _is_valid_webm(file_path):
    """增强的WebM文件验证"""
    try:
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False

        with open(file_path, 'rb') as f:
            # 检查文件大小
            f.seek(0, 2)  # 移动到文件末尾
            file_size = f.tell()
            f.seek(0)  # 回到开头

            if file_size < 100:  # 至少100字节
                logger.warning(f"文件过小: {file_size} bytes")
                return False

            # 检查EBML头
            header = f.read(4)
            if header != b'\x1A\x45\xDF\xA3':
                logger.warning(f"无效的EBML头: {header.hex()}")
                return False

            # 读取更多数据以进行深度验证
            f.seek(0)
            initial_data = f.read(min(2048, file_size))

            # 检查WebM/Matroska标识
            has_webm_marker = (
                    b'webm' in initial_data.lower() or
                    b'matroska' in initial_data.lower() or
                    b'\x42\x82' in initial_data  # DocType element
            )

            if not has_webm_marker:
                logger.warning("未发现WebM/Matroska标识，但继续处理")
                # 仍然返回True，让FFmpeg尝试处理

            logger.info(f"WebM文件验证通过: {file_path}, 大小: {file_size} bytes")
            return True

    except Exception as e:
        logger.error(f"验证WebM文件时出错: {str(e)}")
        return False


async def process_live_media(session_id, base64_data, timestamp, user_id, media_type):
    """处理前端发送的实时媒体数据"""
    try:
        logger.info(f"开始处理{media_type}数据，session_id: {session_id}")

        # 使用安全的base64解码
        webm_bytes = safe_base64_decode(base64_data)
        if webm_bytes is None:
            return {"success": False, "error": "Base64解码失败"}

        # 验证解码后的数据大小
        data_size = len(webm_bytes)
        logger.info(f"解码后数据大小: {data_size} bytes")

        if data_size < 100:  # 至少100字节
            logger.error(f"解码后数据过小: {data_size} bytes")
            return {"success": False, "error": "数据不完整或过小"}

        # 验证WebM文件头
        if not webm_bytes.startswith(b'\x1A\x45\xDF\xA3'):
            logger.error(f"无效的WebM文件头: {webm_bytes[:4].hex()}")
            return {"success": False, "error": "WebM文件头无效"}

        # 保存到文件系统
        file_path = await sync_to_async(_save_media_to_filesystem)(
            session_id, webm_bytes, timestamp, media_type
        )

        # 验证保存的文件
        try:
            full_path = default_storage.path(file_path)
            if not _is_valid_webm(full_path):
                logger.error("保存的WebM文件验证失败")
                # 清理无效文件
                if default_storage.exists(file_path):
                    await sync_to_async(default_storage.delete)(file_path)
                return {"success": False, "error": "WebM文件格式验证失败"}
        except Exception as e:
            logger.warning(f"文件路径获取失败，跳过验证: {str(e)}")

        # 根据媒体类型选择处理方式
        if media_type == "audio":
            asyncio.create_task(_process_audio_data(session_id, file_path, timestamp))
        elif media_type == "video":
            asyncio.create_task(_process_video_data(session_id, file_path, timestamp))

        logger.info(f"{media_type}数据处理任务已启动")
        return {"success": True, "message": f"{media_type}数据接收成功"}

    except Exception as e:
        logger.error(f"处理{media_type}数据失败: {str(e)}", exc_info=True)
        return {"success": False, "error": f"处理失败: {str(e)}"}


def _save_media_to_filesystem(session_id, data, timestamp, media_type):
    """根据媒体类型保存到不同目录"""
    # 根据媒体类型选择保存目录
    if media_type == "audio":
        save_dir = "audio_chunks"
    elif media_type == "video":
        save_dir = "video_chunks"
    else:
        save_dir = "media_chunks"

    file_name = f"interview_{session_id}_{timestamp}_{media_type}_{os.urandom(8).hex()}.webm"
    file_path = default_storage.save(f"{save_dir}/{file_name}", ContentFile(data, name=file_name))
    logger.info(f"文件保存成功: {file_path}")
    return file_path


async def _process_audio_data(session_id, file_path, timestamp):
    """专门处理音频数据，避免重复保存"""
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        logger.info(f"开始处理音频数据: {file_path}")

        # 从已保存的文件中读取数据
        with default_storage.open(file_path, 'rb') as f:
            webm_bytes = f.read()

        logger.info(f"读取音频文件大小: {len(webm_bytes)} bytes")

        # 提取音频数据（传入bytes数据，不是base64字符串）
        audio_bytes = await _extract_audio_from_webm(webm_bytes)
        if not audio_bytes:
            logger.error("语音识别：无音频数据可提取")
            return

        logger.info(f"提取音频数据大小: {len(audio_bytes)} bytes")

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
        session = await sync_to_async(InterviewSession.objects.get)(id=session_id)
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
            analysis_timestamp=timestamp
        )

        # 评估回答并生成新问题
        await evaluate_and_generate_question(session, speech_text, analysis)
        logger.info("音频数据处理完成")

    except Exception as e:
        logger.error(f"处理音频数据失败: {str(e)}", exc_info=True)
    finally:
        # 清理原始文件
        if file_path and default_storage.exists(file_path):
            try:
                await sync_to_async(default_storage.delete)(file_path)
                logger.info(f"清理音频文件: {file_path}")
            except Exception as e:
                logger.warning(f"清理音频文件失败: {str(e)}")


async def _process_video_data(session_id, file_path, timestamp):
    """专门处理视频数据，避免重复保存"""
    try:
        logger.info(f"开始处理视频数据: {file_path}")

        # 从已保存的文件中读取数据
        with default_storage.open(file_path, 'rb') as f:
            webm_bytes = f.read()

        logger.info(f"读取视频文件大小: {len(webm_bytes)} bytes")

        # 创建视频专用临时文件
        temp_path = os.path.join(VIDEO_TEMP_DIR, f"video_{timestamp}_{os.urandom(8).hex()}.webm")
        try:
            with open(temp_path, 'wb') as f:
                f.write(webm_bytes)

            # 验证视频文件
            if not _is_valid_webm(temp_path):
                logger.error("处理视频：WebM视频文件验证失败")
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
            # 清理临时文件
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.info(f"清理临时视频文件: {temp_path}")
                except Exception as e:
                    logger.warning(f"删除临时视频文件失败: {str(e)}")

    except Exception as e:
        logger.error(f"处理视频失败: {str(e)}", exc_info=True)
    finally:
        # 清理原始文件
        if file_path and default_storage.exists(file_path):
            try:
                await sync_to_async(default_storage.delete)(file_path)
                logger.info(f"清理视频文件: {file_path}")
            except Exception as e:
                logger.warning(f"清理视频文件失败: {str(e)}")


async def _analyze_video_frames(video_path):
    """分析视频帧获取表情和肢体语言（直接使用文件路径）"""
    try:
        logger.info(f"开始分析视频帧: {video_path}")

        # 验证文件是否有效
        if not _is_valid_webm(video_path):
            logger.error("分析视频：WebM视频文件验证失败")
            return {"success": False, "error": "无效的视频文件格式", "data": []}

        # 使用OpenCV打开视频
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            # 尝试用FFmpeg后端打开
            cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                logger.error("无法打开视频文件")
                return {"success": False, "error": "无法打开视频文件", "data": []}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_count = 0
        results = []
        facial_analyzer = FacialExpressionAnalyzer()
        last_analysis_time = time.time()

        logger.info(f"视频帧率: {fps}, 开始逐帧分析")

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
                        logger.info(f"分析帧 {frame_count}，时间戳: {frame_count / fps:.2f}s")
                    last_analysis_time = current_time
                except Exception as e:
                    logger.error(f"分析视频帧失败: {str(e)}")

            frame_count += 1

        cap.release()
        logger.info(f"视频分析完成，共处理{frame_count}帧，有效分析{len(results)}帧")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"视频分析失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "data": []}


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
        available = proc.returncode == 0
        logger.info(f"FFmpeg可用性检查: {'可用' if available else '不可用'}")
        return available

    except FileNotFoundError:
        logger.warning("FFmpeg未找到（FileNotFoundError）")
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
            logger.info("FFmpeg可用（同步检查）")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("FFmpeg不可用（同步检查失败）")
            return False


async def has_audio_stream(file_path):
    """检查文件是否包含音频流"""
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
        has_audio = 'audio' in result.stdout
        logger.info(f"音频流检查 {file_path}: {'有音频' if has_audio else '无音频'}")
        return has_audio
    except Exception as e:
        logger.error(f"检查音频流时出错: {e}")
        return False


async def _extract_audio_from_webm(webm_data):
    """提取音频（修复重复解码问题）"""
    if not await _check_ffmpeg_available():
        logger.error("FFmpeg未安装或不在系统PATH中，请先安装FFmpeg")
        return None

    webm_path = None
    audio_path = None
    try:
        # webm_data现在应该已经是bytes类型（在process_live_media中已解码）
        if isinstance(webm_data, str):
            # 如果仍然是字符串，尝试解码（备用处理）
            logger.warning("音频提取：接收到字符串数据，尝试解码")
            webm_bytes = safe_base64_decode(webm_data)
            if webm_bytes is None:
                logger.error("音频提取：Base64解码失败")
                return None
        else:
            webm_bytes = webm_data

        # 验证数据完整性
        data_size = len(webm_bytes)
        logger.info(f"音频提取：处理数据大小 {data_size} bytes")

        if data_size < 100:
            logger.error(f"音频数据过小: {data_size} bytes")
            return None

        # 验证WebM文件头
        if not webm_bytes.startswith(b'\x1A\x45\xDF\xA3'):
            logger.error(f"音频提取：无效的WebM文件头: {webm_bytes[:4].hex()}")
            return None

        # 生成音频专用目录下的 webm 临时文件
        webm_filename = f"audio_extract_{os.urandom(8).hex()}_temp.webm"
        webm_path = os.path.join(AUDIO_TEMP_DIR, webm_filename)

        # 以二进制模式写入文件
        with open(webm_path, 'wb') as f:
            f.write(webm_bytes)

        logger.info(f"创建音频临时WebM文件: {webm_path}")

        # 验证文件是否有效
        if not _is_valid_webm(webm_path):
            logger.error("提取音频：WebM文件验证失败")
            return None

        # 检查文件大小
        file_size = os.path.getsize(webm_path)
        if file_size < 100:  # 小于100字节视为无效
            logger.error(f"文件过小({file_size}字节)，可能不完整")
            return None

        if not await has_audio_stream(webm_path):
            logger.warning("输入的WebM文件不包含音频流")
            # 不直接返回None，让FFmpeg尝试处理

        # 生成音频专用目录下的 mp3 临时文件
        mp3_filename = f"audio_extract_{os.urandom(8).hex()}_temp.mp3"
        audio_path = os.path.join(AUDIO_TEMP_DIR, mp3_filename)

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
            return None

        # 验证输出文件
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            logger.error("输出MP3文件创建失败或为空")
            return None

        output_size = os.path.getsize(audio_path)
        logger.info(f"音频提取成功，输出文件大小: {output_size} bytes")

        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()

        return audio_bytes

    except Exception as e:
        logger.error(f"提取音频失败: {str(e)}", exc_info=True)
        return None
    finally:
        # 清理临时文件
        for path in [webm_path, audio_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.info(f"清理临时文件: {path}")
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

        logger.info(f"视频转换成功: {output_path}")

    except Exception as e:
        logger.error(f"转换视频失败: {str(e)}", exc_info=True)
        raise


async def generate_initial_question(session):
    """生成初始面试问题"""
    try:
        logger.info(f"为会话 {session.id} 生成初始问题")

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

            logger.info(f"生成问题: {new_question_text[:50]}...")

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
                logger.info("初始问题发送成功")
            else:
                logger.error("音频生成失败")
        else:
            logger.error("生成初始问题失败")
    except Exception as e:
        logger.error(f"生成初始问题时出错: {str(e)}", exc_info=True)


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
                await send_audio_and_text_to_client(session.id, audio_result["audio_data"],
                                                    new_question_text)  # 修改调用的函数名
        else:
            logger.error("生成新问题失败")
    else:
        logger.error("评估回答失败")
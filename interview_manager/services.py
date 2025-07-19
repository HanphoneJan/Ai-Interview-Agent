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

async def process_live_media(session_id, base64_data, timestamp, user_id, media_type):
    """处理前端发送的实时媒体数据"""
    try:
        logger.info(f"开始处理{media_type}数据，session_id: {session_id}")

        # 使用安全的base64解码
        audio_bytes = safe_base64_decode(base64_data)
        if audio_bytes is None:
            return {"success": False, "error": "Base64解码失败"}

        # 验证解码后的数据大小
        data_size = len(audio_bytes)
        logger.info(f"解码后PCM数据大小: {data_size} bytes")

        if data_size < 100:  # 至少100字节
            logger.error(f"解码后数据过小: {data_size} bytes")
            return {"success": False, "error": "数据不完整或过小"}

        # 根据媒体类型选择处理方式
        if media_type == "audio":
            # 直接处理音频并获取识别结果
            result = await _process_audio_data(session_id, audio_bytes, timestamp)
            if result.get("success"):
                return {
                    "success": True,
                    "message": "音频数据接收和处理成功",
                    "answer": result.get("speech_text", "")
                }
            return {"success": False, "error": result.get("error", "音频处理失败")}
        elif media_type == "video":
            # 视频处理保持不变
            file_path = await sync_to_async(_save_media_to_filesystem)(
                session_id, audio_bytes, timestamp, media_type
            )
            asyncio.create_task(_process_video_data(session_id, file_path, timestamp))
            return {"success": True, "message": "视频数据接收成功"}

    except Exception as e:
        logger.error(f"处理{media_type}数据失败: {str(e)}", exc_info=True)
        return {"success": False, "error": f"处理失败: {str(e)}"}


def _save_media_to_filesystem(session_id, data, timestamp, media_type):
    """根据媒体类型保存到不同目录"""
    # 根据媒体类型选择保存目录
    save_dir=""
    if media_type == "audio":
        save_dir = "audio_chunks"
    elif media_type == "video":
        save_dir = "video_chunks"

    file_name = f"interview_{session_id}_{timestamp}_{media_type}_{os.urandom(8).hex()}.webm"
    file_path = default_storage.save(f"{save_dir}/{file_name}", ContentFile(data, name=file_name))
    logger.info(f"文件保存成功: {file_path}")
    return file_path


async def _process_audio_data(session_id, pcm_bytes, timestamp):
    """专门处理PCM音频数据"""
    try:
        logger.info(f"开始处理PCM音频数据，大小: {len(pcm_bytes)} bytes")

        # 直接使用PCM数据进行语音识别
        result = await recognize(pcm_bytes)
        if not result["success"]:
            logger.error(f"语音识别失败: {result.get('error', '未知错误')}")
            return {"success": False, "error": result.get("error", "语音识别失败")}

        speech_text = result["text"]
        logger.info(f"语音识别结果: {speech_text[:50]}...")

        # 计算音频时长（秒）并转换为PostgreSQL interval格式
        # PCM格式假设: 16kHz采样率, 16位深度, 单声道
        duration_seconds = len(pcm_bytes) / (16000 * 2)  # 估算秒数 (采样率*位深)
        duration_interval = f"{duration_seconds} seconds"  # PostgreSQL interval格式

        # 保存识别结果
        session = await sync_to_async(InterviewSession.objects.get)(id=session_id)
        current_question = await sync_to_async(
            InterviewQuestion.objects.filter(session=session).latest
        )('asked_at')

        metadata = await sync_to_async(ResponseMetadata.objects.create)(
            question=current_question,
            audio_duration=duration_interval
        )

        analysis = await sync_to_async(ResponseAnalysis.objects.create)(
            metadata=metadata,
            speech_text=speech_text,
            analysis_timestamp=timestamp
        )

        # 评估回答并生成新问题
        await evaluate_and_generate_question(session, speech_text, analysis)
        logger.info("音频数据处理完成")

        return {"success": True, "speech_text": speech_text}

    except Exception as e:
        logger.error(f"处理音频数据失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


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


async def process_image_data(session_id, base64_data, timestamp):
    """处理图片数据，进行表情分析"""
    try:
        logger.info(f"开始处理图片数据，session_id: {session_id}")

        # 解码base64数据
        image_bytes = safe_base64_decode(base64_data)
        if image_bytes is None:
            return {"success": False, "error": "Base64解码失败"}

        # 保存图片到临时文件
        temp_path = os.path.join(VIDEO_TEMP_DIR, f"image_{timestamp}_{os.urandom(8).hex()}.jpg")
        with open(temp_path, 'wb') as f:
            f.write(image_bytes)

        # 分析图片
        analyzer = FacialExpressionAnalyzer()
        frame = cv2.imread(temp_path)
        if frame is None:
            logger.error("无法读取图片文件")
            return {"success": False, "error": "无法读取图片文件"}

        analysis_result = await asyncio.to_thread(analyzer.analyze_frame, frame)
        print(analysis_result["data"]["face_0"]["expression"])
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except Exception as e:
            logger.warning(f"删除临时图片文件失败: {str(e)}")

        if not analysis_result.get("success"):
            return {"success": False, "error": analysis_result.get("error", "表情分析失败")}

        # 保存分析结果
        session = await sync_to_async(InterviewSession.objects.get)(id=session_id)
        latest_analysis = await sync_to_async(
            ResponseAnalysis.objects.filter(metadata__question__session=session)
            .order_by('-analysis_timestamp').first
        )()

        if latest_analysis:
            latest_analysis.facial_expression = str(analysis_result.get("data", {}))
            await sync_to_async(latest_analysis.save)()

        return {"success": True, "data": analysis_result.get("data", {})}

    except Exception as e:
        logger.error(f"处理图片数据失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}




async def process_text_answer(session_id, answer_text, timestamp):
    """处理文本回答并生成新问题"""
    try:
        logger.info(f"开始处理文本回答，session_id: {session_id}")

        if not answer_text or not answer_text.strip():
            return {"success": False, "error": "回答文本为空"}

        # 获取会话和当前问题
        session = await sync_to_async(InterviewSession.objects.get)(id=session_id)
        current_question = await sync_to_async(
            InterviewQuestion.objects.filter(session=session).latest
        )('asked_at')

        # 创建回答元数据
        metadata = await sync_to_async(ResponseMetadata.objects.create)(
            question=current_question,
            audio_duration="0 seconds"  # 文本回答没有音频时长
        )

        # 创建回答分析记录
        analysis = await sync_to_async(ResponseAnalysis.objects.create)(
            metadata=metadata,
            speech_text=answer_text,
            analysis_timestamp=timestamp
        )

        # 评估回答并生成新问题
        await evaluate_and_generate_question(session, answer_text, analysis)

        logger.info("文本回答处理完成")
        return {"success": True, "message": "文本回答处理成功"}

    except Exception as e:
        logger.error(f"处理文本回答失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


async def generate_initial_question(session):
    """生成初始面试问题"""
    try:
        logger.info(f"为会话 {session.id} 生成初始问题")

        new_question_response = spark_ai_engine.generate_response(
            "假设你现在是一个面试官，正在对一个求职的大学生进行面试，请提出第一个面试问题。要求该问题比较简短。", []
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
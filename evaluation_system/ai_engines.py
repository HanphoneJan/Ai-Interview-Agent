# evaluation_system/ai_engines.py
import asyncio

import aiohttp
import json
import logging
import base64
import hashlib
import hmac
import time
import socketio
from urllib.parse import urlencode
from aiohttp import web

logger = logging.getLogger(__name__)
sio = socketio.AsyncClient()  # 初始化异步Socket.IO客户端


async def generate_signa(appid, api_key, ts):
    """生成讯飞API所需的signa签名（与原逻辑一致）"""
    base_string = appid + ts
    md5_base = hashlib.md5(base_string.encode()).hexdigest()
    signa = hmac.new(
        api_key.encode(),
        md5_base.encode(),
        hashlib.sha1
    ).digest()
    return base64.b64encode(signa).decode()


@sio.on('connect')
async def on_connect():
    """Socket.IO连接成功回调"""
    logger.info('Connected to XFyun RTASR server')


@sio.on('disconnect')
async def on_disconnect():
    """Socket.IO连接断开回调"""
    logger.warning('Disconnected from XFyun RTASR server')


@sio.on('started')
async def on_started(data):
    """接收握手成功事件"""
    if data.get('code') == '0':
        logger.info('Handshake successful')
    else:
        logger.error(f'Handshake failed: {data.get("desc")}')


@sio.on('result')
async def on_result(data):
    """接收转写结果事件"""
    nonlocal result_future
    result_future.set_result(data)


@sio.on('error')
async def on_error(data):
    """接收错误事件"""
    nonlocal result_future
    result_future.set_exception(Exception(f'XFyun error: {data.get("desc")}'))


async def analyze_live_audio(session_id, audio_chunk, appid, api_key, lang="cn", pd="edu"):
    """
    实时分析音频流（基于Socket.IO实现）
    :param session_id: 会话ID
    :param audio_chunk: 音频数据块（16K采样率，16bit PCM格式）
    :param appid: 讯飞开放平台应用ID
    :param api_key: 讯飞接口密钥
    :param lang: 语种标识（默认中文）
    :param pd: 垂直领域参数（默认教育领域）
    :return: 转写文本及置信度
    """
    global result_future  # 用于异步等待结果
    ts = str(int(time.time()))
    signa = await generate_signa(appid, api_key, ts)
    params = {
        "appid": appid,
        "ts": ts,
        "signa": signa,
        "lang": lang,
        "pd": pd
    }
    url = f"wss://rtasr.xfyun.cn/v1/ws?{urlencode(params)}"

    try:
        # 建立Socket.IO连接（强制使用WebSocket传输）
        await sio.connect(url, transports=['websocket'], auth=params)

        # 初始化异步结果等待
        result_future = sio.loop.create_future()

        # 发送音频数据（使用binary=True发送二进制数据）
        await sio.emit('audio_chunk', audio_chunk, binary=True)

        # 等待结果返回（超时30秒）
        response = await asyncio.wait_for(result_future, timeout=30)

        # 解析结果（与原逻辑一致）
        if response.get('action') == "result" and response.get('code') == "0":
            data = json.loads(response.get("data", "{}"))
            if "cn" in data:
                words = [word_obj["cw"][0]["w"] for word_obj in data["cn"]["st"]["rt"][0]["ws"]]
                return {
                    "session_id": session_id,
                    "text": "".join(words),
                    "confidence": 0.7 if data["cn"]["st"]["type"] == "1" else 0.9,
                    "is_final": data["cn"]["st"]["type"] == "0"
                }
            elif "biz" in data and data["biz"] == "trans":
                return {
                    "session_id": session_id,
                    "text": data["dst"],
                    "confidence": 0.8,
                    "is_final": not data["isEnd"]
                }

        return {
            "session_id": session_id,
            "text": "",
            "confidence": 0,
            "error": response.get("desc", "Unknown response")
        }

    except asyncio.TimeoutError:
        logger.error("XFyun API response timeout")
        return {
            "session_id": session_id,
            "text": "",
            "confidence": 0,
            "error": "Response timeout"
        }
    except socketio.exceptions.ConnectionError as e:
        logger.error(f"Socket.IO connection error: {e}")
        return {
            "session_id": session_id,
            "text": "",
            "confidence": 0,
            "error": "Connection failed"
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "session_id": session_id,
            "text": "",
            "confidence": 0,
            "error": str(e)
        }
    finally:
        # 确保断开连接
        try:
            await sio.disconnect()
        except:
            pass


async def analyze_facial_expression(video_chunk):
    """面部表情分析（保持原逻辑）"""
    try:
        pass
    except Exception as e:
        logger.error(f"Facial analysis error: {e}")
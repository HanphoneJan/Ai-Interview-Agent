# evaluation_system/ai_engines.py
import asyncio
import math
import os
import time
import base64
import hashlib
import hmac
from urllib.parse import urlparse, urlencode
from datetime import datetime
import aiohttp
import json
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
logger = logging.getLogger(__name__)


def get_credentials():
    """获取讯飞API凭证"""
    appid = os.getenv("XF_APPID")
    api_key = os.getenv("XF_APP_KEY")
    api_secret = os.getenv("XF_APP_SECRET")

    if not all([appid, api_key, api_secret]):
        raise ValueError("缺少讯飞API凭证(XF_APPID, XF_APP_KEY, XF_APP_SECRET)")
    return appid, api_key, api_secret


def hmac_sha256(data, key):
    """计算HMAC-SHA256签名"""
    return hmac.new(
        key.encode(),
        data.encode(),
        hashlib.sha256
    ).digest()


def assemble_auth_url(hosturl, api_key, api_secret):
    """生成鉴权URL（符合新鉴权规范）"""
    # 解析URL
    parsed_url = urlparse(hosturl)
    host = parsed_url.hostname
    path = parsed_url.path

    # 获取UTC时间
    date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    # 拼接签名字符串
    sign_strings = [
        f"host: {host}",
        f"date: {date}",
        f"GET {path} HTTP/1.1"
    ]
    sign_string = "\n".join(sign_strings)
    logger.debug(f"签名字符串: \n{sign_string}")

    # 计算HMAC-SHA256签名
    signature = hmac_sha256(sign_string, api_secret)
    signature_base64 = base64.b64encode(signature).decode()
    logger.debug(f"签名结果: {signature_base64}")

    # 构建authUrl
    auth_url = f"api_key=\"{api_key}\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"{signature_base64}\""
    logger.debug(f"authUrl: {auth_url}")

    # Base64编码authorization
    authorization = base64.b64encode(auth_url.encode()).decode()
    logger.debug(f"authorization: {authorization}")

    # 构建最终URL
    params = {
        "host": host,
        "date": date,
        "authorization": authorization
    }
    query_string = urlencode(params)
    final_url = f"{hosturl}?{query_string}"
    logger.info(f"最终鉴权URL: {final_url}")

    return final_url, date


async def recognize(audio_data, lang="cn", pd="general"):
    """
    实时语音识别主函数
    audio_data: 16kHz 16位单声道PCM音频数据
    """
    appid, api_key, api_secret = get_credentials()
    hosturl = "ws://iat-api.xfyun.cn/v2/iat"
    session_id = f"sid-{int(time.time() * 1000)}"

    # 生成鉴权URL
    auth_url, date = assemble_auth_url(hosturl, api_key, api_secret)

    try:
        async with aiohttp.ClientSession() as session:
            # 设置超时
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.ws_connect(auth_url, timeout=timeout) as ws:
                # 发送握手消息（包含session_id和语言参数）
                handshake = {
                    "action": "start",
                    "data": {
                        "appid": appid,
                        "language": lang,
                        "domain": pd,
                        "session_id": session_id,
                        "data_type": "audio",
                        "sample_rate": 16000
                    }
                }
                await ws.send_str(json.dumps(handshake))
                logger.info("已发送握手请求")

                # 处理握手响应
                handshake_resp = await ws.receive()
                if handshake_resp.type != aiohttp.WSMsgType.TEXT:
                    raise ValueError(f"握手响应异常: {handshake_resp.type}")

                resp_data = json.loads(handshake_resp.data)
                if resp_data.get("code") != "0":
                    raise ValueError(f"握手失败: {resp_data.get('desc', '未知错误')}")
                logger.info(f"握手成功: {resp_data}")

                # 发送音频数据
                audio_base64 = base64.b64encode(audio_data).decode()
                audio_msg = {
                    "action": "audio",
                    "data": {
                        "audio": audio_base64,
                        "encoding": "raw",
                        "sample_rate": 16000,
                        "session_id": session_id
                    }
                }
                await ws.send_str(json.dumps(audio_msg))
                logger.info("已发送音频数据")

                # 接收识别结果
                results = []
                while True:
                    msg = await ws.receive()
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue

                    data = json.loads(msg.data)
                    if data.get("action") == "result":
                        # 解析中文识别结果
                        if "cn" in data.get("data", {}):
                            result_data = json.loads(data["data"])
                            words = [word["cw"][0]["w"] for word in result_data["cn"]["st"]["rt"][0]["ws"]]
                            is_final = result_data["cn"]["st"]["type"] == "0"
                            results.append("".join(words))
                            if is_final:
                                break
                        # 解析其他语言结果（如英文）
                        elif "biz" in data.get("data", {}):
                            result_data = json.loads(data["data"])
                            results.append(result_data["dst"])
                            if not result_data.get("isEnd", True):
                                break

                # 发送结束消息
                end_msg = {
                    "action": "end",
                    "data": {"session_id": session_id}
                }
                await ws.send_str(json.dumps(end_msg))
                logger.info("已发送结束请求")

                return {
                    "text": "".join(results),
                    "session_id": session_id,
                    "success": True
                }

    except aiohttp.ClientError as e:
        logger.error(f"网络错误: {e}")
        return {"error": f"网络错误: {e}", "success": False}
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        return {"error": f"参数错误: {e}", "success": False}
    except Exception as e:
        logger.error(f"未知错误: {e}")
        return {"error": f"未知错误: {e}", "success": False}


async def generate_test_audio(duration=1.0):
    """生成16kHz 16位单声道PCM测试音频"""
    import struct
    sample_rate = 16000
    num_samples = int(sample_rate * duration)
    audio_data = b""
    for i in range(num_samples):
        # 生成440Hz正弦波
        t = i / sample_rate
        value = int(16384 * math.sin(2 * math.pi * 440 * t))
        audio_data += struct.pack("h", value)
    return audio_data


async def recognition():
    """测试语音识别功能"""
    audio_data = await generate_test_audio()
    result = await recognize(audio_data, pd="general")  # 使用通用领域

    print("识别结果:")
    if result["success"]:
        print(f"文本: {result['text']}")
    else:
        print(f"错误: {result['error']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    asyncio.run(recognition())
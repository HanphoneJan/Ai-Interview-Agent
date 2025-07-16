# test_ai_engines.py
import json

import pytest
import asyncio
import base64
import hashlib
import hmac
from unittest.mock import patch, MagicMock

import socketio

from evaluation_system.evaluate_engine import (
    analyze_live_audio,
    generate_signa,
    sio,
    result_futures
)

# 配置日志以便调试
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_generate_signa():
    """测试签名生成函数，确保与实际计算一致"""
    appid = "test_appid"
    api_key = "test_api_key"
    ts = "1625100000"

    # 手动计算预期签名（模拟真实场景）
    base_string = appid + ts
    md5_digest = hashlib.md5(base_string.encode()).hexdigest()
    hmac_digest = hmac.new(
        api_key.encode(),
        md5_digest.encode(),
        hashlib.sha1
    ).digest()
    expected_signa = base64.b64encode(hmac_digest).decode()

    result = await generate_signa(appid, api_key, ts)
    assert result == expected_signa, f"签名不匹配，预期: {expected_signa}, 实际: {result}"


@pytest.mark.asyncio
async def test_analyze_live_audio_success():
    session_id = "test_session"
    appid = "test_appid"
    api_key = "test_api_key"
    audio_chunk = b"mock_audio_data"

    with patch.object(sio, 'connect') as mock_connect, \
            patch.object(sio, 'emit') as mock_emit, \
            patch.object(sio, 'disconnect') as mock_disconnect:
        mock_connect.return_value = None
        mock_emit.return_value = None
        mock_disconnect.return_value = None

        # 完整模拟讯飞API响应结构
        mock_result = {
            "action": "result",
            "code": "0",
            "session_id": session_id,
            "data": json.dumps({
                "cn": {
                    "st": {
                        "rt": [
                            {
                                "ws": [
                                    {
                                        "bg": 0,
                                        "ed": 400,
                                        "cw": [{"w": "你好", "sc": 95}]
                                    },
                                    {
                                        "bg": 400,
                                        "ed": 800,
                                        "cw": [{"w": "世界", "sc": 96}]
                                    }
                                ]
                            }
                        ],
                        "type": "0"
                    }
                }
            })
        }

        result_futures[session_id] = asyncio.Future()
        result_futures[session_id].set_result(mock_result)

        result = await analyze_live_audio(
            session_id, audio_chunk, appid, api_key
        )

        # 验证结果
        assert result["text"] == "你好世界", f"文本解析失败，实际: {result['text']}"
        assert result["confidence"] == 0.9, "置信度计算错误"
        assert result["is_final"] is True, "最终结果标识错误"


@pytest.mark.asyncio
async def test_analyze_live_audio_timeout():
    """测试请求超时场景"""
    session_id = "timeout_session"
    appid = "test_appid"
    api_key = "test_api_key"
    audio_chunk = b"mock_audio_data"

    with patch.object(sio, 'connect') as mock_connect, \
            patch.object(sio, 'emit') as mock_emit:
        mock_connect.return_value = None
        mock_emit.return_value = None

        # 创建不会完成的Future
        result_futures[session_id] = asyncio.Future()

        # 调用函数并捕获结果
        result = await analyze_live_audio(
            session_id, audio_chunk, appid, api_key
        )

        # 验证错误处理
        assert result["error"] == "Response timeout", "超时错误处理失败"
        assert "text" in result and result["text"] == "", "文本结果应为空"

        # 清理资源
        if session_id in result_futures:
            del result_futures[session_id]


@pytest.mark.asyncio
async def test_analyze_live_audio_connection_error():
    """测试连接失败场景"""
    session_id = "error_session"
    appid = "test_appid"
    api_key = "test_api_key"
    audio_chunk = b"mock_audio_data"

    with patch.object(sio, 'connect') as mock_connect, \
            patch.object(sio, 'disconnect') as mock_disconnect:
        # 设置连接抛出异常
        mock_connect.side_effect = socketio.exceptions.ConnectionError("模拟连接失败")
        mock_disconnect.return_value = None

        # 调用函数并捕获结果
        result = await analyze_live_audio(
            session_id, audio_chunk, appid, api_key
        )

        # 验证错误处理
        assert result["error"] == "Connection failed", "连接错误处理失败"
        assert "text" in result and result["text"] == "", "文本结果应为空"

        # 清理资源
        if session_id in result_futures:
            del result_futures[session_id]
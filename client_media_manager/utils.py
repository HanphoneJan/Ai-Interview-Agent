# client_media_manager/utils.py
import json
import asyncio
from channels.layers import get_channel_layer

async def send_audio_to_client(session_id, audio_data):
    channel_layer = get_channel_layer()
    group_name = f"interview_session_{session_id}"
    await channel_layer.group_send(
        group_name,
        {
            "type": "send_audio",
            "audio_data": audio_data
        }
    )

# interview_manager/services.py
def get_media_servers_config(scenario_id):
    """获取场景对应的媒体服务器配置（STUN/TURN地址）"""
    scenario = InterviewScenario.objects.get(id=scenario_id)
    return {
        "iceServers": [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": "turn:turn-server.example.com:3478",
             "username": "user", "credential": "pass"}
        ],
        "mediaConstraints": scenario.media_config
    }
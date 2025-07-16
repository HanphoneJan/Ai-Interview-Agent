# 移除未使用的导入语句
# from django.conf import settings
from sparkai.llm.llm import ChatSparkLLM, ChunkPrintHandler
from sparkai.core.messages import ChatMessage

import os
from dotenv import load_dotenv
import logging

# 加载.env文件中的环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SparkAIEngine:
    """星火认知大模型调用引擎（基于Spark Pro版本）"""

    def __init__(self):
        """初始化配置，从环境变量读取密钥信息"""
        # 从环境变量加载密钥
        self.app_id = os.getenv("XF_APP_ID")
        self.api_key = os.getenv("XF_APP_KEY")
        self.api_secret = os.getenv("XF_APP_SECRET")

        # 检查必要的环境变量是否已设置
        if not all([self.app_id, self.api_key, self.api_secret]):
            error_msg = "请设置星火大模型API所需的环境变量：XF_APP_ID, XF_APP_KEY, XF_APP_SECRET"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 打印配置信息用于调试
        logger.info(f"星火大模型配置：APP_ID={self.app_id[:3]}***{self.app_id[-3:]}")

        # 固定配置（Spark Pro版本）
        self.spark_url = "wss://spark-api.xf-yun.com/v3.1/chat"
        self.domain = "generalv3"  # 与v3.1/chat地址匹配的domain

        # 初始化大模型客户端
        self.client = self._init_client()

    def _init_client(self) -> ChatSparkLLM:
        """初始化星火大模型客户端"""
        return ChatSparkLLM(
            spark_api_url=self.spark_url,
            spark_app_id=self.app_id,
            spark_api_key=self.api_key,
            spark_api_secret=self.api_secret,
            spark_llm_domain=self.domain,
            streaming=False  # 非流式返回模式
        )

    def generate_response(self, user_query: str, history: list = None) -> dict:
        """
        生成模型响应

        参数:
            user_query: 当前用户输入
            history: 历史对话列表，格式为[{"role": "user/assistant", "content": "xxx"}, ...]

        返回:
            包含响应内容和token消耗的字典
        """
        try:
            # 构建对话消息列表
            messages = []

            # 处理历史对话
            if history:
                for item in history:
                    messages.append(
                        ChatMessage(
                            role=item["role"],
                            content=item["content"]
                        )
                    )

            # 添加当前查询
            messages.append(
                ChatMessage(
                    role="user",
                    content=user_query
                )
            )

            # 添加回调处理器以获取流式输出
            handler = ChunkPrintHandler()
            response = self.client.generate([messages], callbacks=[handler])

            # 检查响应是否有效
            if not response.generations or not response.generations[0] or not response.generations[0][0]:
                error_msg = "生成的响应内容为空"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # 解析响应结果
            token_usage = response.llm_output.get("token_usage", {})
            result = {
                "success": True,
                "content": response.generations[0][0].message.content,
                "usage": {
                    "prompt_tokens": token_usage.get('prompt_tokens', 0),
                    "completion_tokens": token_usage.get('completion_tokens', 0),
                    "total_tokens": token_usage.get('total_tokens', 0)
                }
            }
            return result

        except Exception as e:
            # 记录详细错误信息
            logger.exception("生成响应时发生错误")
            return {
                "success": False,
                "error": f"系统错误: {str(e)}"
            }

    def generate_stream_response(self, user_query: str, history: list = None):
        """
        生成流式响应（用于实时返回）

        参数:
            user_query: 当前用户输入
            history: 历史对话列表

        返回:
            生成器对象，逐个返回响应片段
        """
        try:
            messages = []
            if history:
                for item in history:
                    messages.append(
                        ChatMessage(role=item["role"], content=item["content"])
                    )
            messages.append(ChatMessage(role="user", content=user_query))

            # 启用流式模式
            stream_client = ChatSparkLLM(
                spark_api_url=self.spark_url,
                spark_app_id=self.app_id,
                spark_api_key=self.api_key,
                spark_api_secret=self.api_secret,
                spark_llm_domain=self.domain,
                streaming=True
            )

            # 流式返回
            yielded = False
            for chunk in stream_client._stream(messages):
                if chunk.message.content:
                    yield chunk.message.content
                    yielded = True

            # 如果没有产生任何内容，返回错误
            if not yielded:
                yield "错误: 没有从模型获取到任何内容"

        except Exception as e:
            logger.exception("生成流式响应时发生错误")
            yield f"错误: {str(e)}"


# 初始化引擎实例（全局单例）
spark_ai_engine = SparkAIEngine()


def main():
    """测试SparkAIEngine类的功能"""
    # 从环境变量读取配置或使用默认值
    app_id = os.getenv("XF_APP_ID", "your_spark_app_id")
    api_key = os.getenv("XF_APP_KEY", "your_spark_api_key")
    api_secret = os.getenv("XF_APP_SECRET", "your_spark_api_secret")

    # 设置环境变量
    os.environ["XF_APP_ID"] = app_id
    os.environ["XF_APP_KEY"] = api_key
    os.environ["XF_APP_SECRET"] = api_secret

    print(f"使用APP_ID: {app_id[:3]}***{app_id[-3:]} 进行测试")

    try:
        # 初始化引擎
        engine = SparkAIEngine()

        # 测试非流式响应
        print("\n=== 测试非流式响应 ===")
        user_query = "你好，请介绍一下自己"
        response = engine.generate_response(user_query)

        if response["success"]:
            print(f"用户查询: {user_query}")
            print(f"模型回复: {response['content']}")
            print(f"Token使用: {response['usage']['total_tokens']} tokens")
        else:
            print(f"错误: {response['error']}")

        # 测试流式响应
        print("\n=== 测试流式响应 ===")
        stream_response = engine.generate_stream_response("请简要介绍一下Python编程语言")

        print("流式输出:")
        for chunk in stream_response:
            print(chunk, end="", flush=True)
        print()

        # 测试带历史对话的响应
        print("\n=== 测试带历史对话的响应 ===")
        history = [
            {"role": "user", "content": "Python是什么时候创建的？"},
            {"role": "assistant", "content": "Python由吉多·范罗苏姆于1989年圣诞节期间创建。"}
        ]

        response_with_history = engine.generate_response("它的主要设计理念是什么？", history)

        if response_with_history["success"]:
            print("历史对话:")
            for msg in history:
                print(f"{msg['role']}: {msg['content']}")
            print(f"当前回复: {response_with_history['content']}")
        else:
            print(f"错误: {response_with_history['error']}")

    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")


if __name__ == "__main__":
    main()
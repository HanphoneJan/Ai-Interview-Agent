#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # 加载环境变量
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AiInterviewAgent.settings")

    # 从环境变量获取端口，如果未设置则使用默认值8000
    DEFAULT_PORT = "8000"
    SERVER_PORT = os.getenv('SERVER_PORT', DEFAULT_PORT)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django."
        ) from exc

    # 无论是否指定端口，都使用环境变量中的端口
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        # 移除命令行中可能存在的端口参数
        if len(sys.argv) > 2:
            print(f"Ignoring command-line port {sys.argv[2]}")
            sys.argv = sys.argv[:2]

        # 添加环境变量中的端口
        sys.argv.append(SERVER_PORT)
        print(f"Using port {SERVER_PORT} from environment variable")

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
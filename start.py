#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爱通知小爱音箱消息推送统一API平台启动脚本
快速启动开发服务器
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import main

if __name__ == "__main__":
    main()

#!/bin/bash

# 安装依赖
pip install -r requirements.txt

# 创建数据库
python -c "from client.database import DatabaseManager; db = DatabaseManager()"

# 启动程序
python client/main.py 
# -*- coding: utf-8 -*-
"""
配置文件示例
复制此文件为 config.py 并填入真实配置

注意：敏感信息请使用环境变量管理，不要提交到代码仓库！
"""

# ============== 邮件配置 ==============

# Gmail 配置
# 使用Gmail时，需要启用"应用专用密码"
# https://support.google.com/accounts/answer/185833
SENDER_EMAIL = "your_email@gmail.com"
# 推荐使用环境变量: export GMAIL_SMTP_PASSWORD="your_app_password"
GMAIL_SMTP_PASSWORD = ""  # 不要硬编码！

# QQ邮箱配置 (可选)
# QQ邮箱SMTP授权码获取: https://mail.qq.com/cgi-bin/authmgr
QQ_EMAIL = "your_qq@qq.com"
# 推荐使用环境变量: export QQ_SMTP_PASSWORD="your_auth_code"
QQ_SMTP_PASSWORD = ""  # 不要硬编码！

# 收件人列表
RECIPIENTS = [
    "your_email1@example.com",
    "your_email2@example.com",
]

# ============== 股票配置 ==============

# 关注的股票列表 (可自定义)
STOCKS = [
    {"code": "300666", "name": "江丰电子"},
    {"code": "000778", "name": "新兴铸管"},
    {"code": "601990", "name": "南京证券"},
    {"code": "001369", "name": "双欣环保"},
    {"code": "600121", "name": "郑州煤电"},
    {"code": "601398", "name": "工商银行"},
    # ETF
    {"code": "159518", "name": "标普油气ETF嘉实"},
    {"code": "159609", "name": "光伏ETF浦银"},
    {"code": "159636", "name": "港股通科技30ETF工银"},
    {"code": "159672", "name": "消费ETF博时"},
]

# ============== 高级配置 ==============

# 报告输出目录
REPORT_DIR = "/home/zhiping/.openclaw/workspace/reports"

# 是否使用代理 (默认不使用)
USE_PROXY = False
PROXY_URL = "http://127.0.0.1:7890"

# 数据源优先级 (按顺序尝试)
DATA_SOURCES = [
    "tencent",   # 腾讯财经
    "akshare",   # AKShare
    "eastmoney", # 东方财富
    "sina",      # 新浪财经
]

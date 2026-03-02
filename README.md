# A股每日报告 (A-Stock Daily Report)

自动获取A股股票数据，生成每日分析报告并发送到邮箱。

## 功能特性

- 多数据源支持：腾讯财经 > AKShare > 东方财富 > 新浪财经
- 技术指标：MA均线、MACD、KDJ、RSI、布林带、OBV等
- 支持A股股票和ETF
- 自动判断是否为交易日
- 邮件发送（支持QQ邮箱和Gmail）

## 配置文件

复制 `config.example.py` 为 `config.py` 并填入配置：

```bash
cp config.example.py config.py
# 然后编辑 config.py 填入你的配置
```

或设置环境变量：

```bash
export GMAIL_SMTP_PASSWORD="your_gmail_app_password"
export QQ_SMTP_PASSWORD="your_qq_smtp授权码"
```

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 手动运行
python a_stock_daily.py

# 测试模式（不检查交易日）
python a_stock_daily.py --test
```

## 定时任务 (可选)

使用 crontab 每日早上9点运行：

```bash
0 9 * * 1-5 cd /path/to/a-stock-daily-report && python a_stock_daily.py >> /path/to/reports.log 2>&1
```

## 股票列表

默认包含10只股票/ETF，可按需修改 `STOCKS` 列表。

## 数据来源

- 腾讯财经API
- AKShare
- 东方财富
- 新浪财经

## 注意事项

- 请勿将包含真实密码的代码推送到公开仓库
- 使用环境变量或 `.env` 文件管理敏感信息
- 尊重数据源的使用条款和限制

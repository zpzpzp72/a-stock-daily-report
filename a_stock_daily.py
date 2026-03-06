#!/usr/bin/env python3
"""
A股 Daily Report - 每日股票分析报告
使用多数据源获取最新行情和技术指标（新浪财经、东方财富、腾讯财经）
"""

import os
import sys
import smtplib
import time
from datetime import datetime, timedelta, date
import requests
import urllib3
urllib3.disable_warnings()
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# 设置 Gmail 密码
os.environ.setdefault("GMAIL_SMTP_PASSWORD", "lepyvjiimtfmsqpv")

# 不使用代理

# 判断是否为ETF (ETF代码通常以 15xxxx 开头)
def is_etf(code):
    """判断股票代码是否为ETF"""
    return code.startswith("15") or code.startswith("16") or code.startswith("17")

# 股票列表
STOCKS = [
    {"code": "300666", "name": "江丰电子"},
    {"code": "000778", "name": "新兴铸管"},
    {"code": "601990", "name": "南京证券"},
    {"code": "001369", "name": "双欣环保"},
    {"code": "600121", "name": "郑州煤电"},
    {"code": "601398", "name": "工商银行"},
    {"code": "159518", "name": "标普油气ETF嘉实"},
    {"code": "159609", "name": "光伏ETF浦银"},
    {"code": "159636", "name": "港股通科技30ETF工银"},
    {"code": "159672", "name": "消费ETF博时"},
]

RECIPIENTS = ["9892890@qq.com", "42194972@qq.com"]
# 默认发件：QQ邮箱 (主)，Gmail (备份)
# 发送逻辑：先尝试QQ-SMTP，失败则自动切换到Gmail-SMTP
QQ_SENDER_EMAIL = "9892890@qq.com"
QQ_SMTP_PASSWORD = "dqwervcgpylbbgcg"
GMAIL_SENDER_EMAIL = "zhiping2007@gmail.com"

# 全局交易日历缓存
_trade_calendar_cache = None


def _get_trade_calendar():
    """获取A股交易日历（全局缓存，只调用一次）
    
    使用纯算法计算：排除周末和常见节假日。
    由于AKShare在WSL中无法访问，改用本地算法计算。
    """
    global _trade_calendar_cache
    
    if _trade_calendar_cache is not None:
        return _trade_calendar_cache
    
    import pandas as pd
    from datetime import datetime, timedelta
    
    print("计算A股交易日历（本地算法）...")
    
    # 生成过去2年和未来1年的所有日期
    today = datetime.now()
    start_date = today - timedelta(days=730)  # 过去2年
    end_date = today + timedelta(days=365)    # 未来1年
    
    # 中国2025-2026年主要节假日（简单估算）
    holidays = [
        # 2025年
        '2025-01-01', '2025-01-28', '2025-01-29', '2025-01-30', '2025-01-31',
        '2025-02-01', '2025-02-02', '2025-02-03', '2025-02-04',
        '2025-04-04', '2025-04-05', '2025-04-06',
        '2025-05-01', '2025-05-02', '2025-05-03',
        '2025-06-09', '2025-06-10',
        '2025-09-15', '2025-09-16', '2025-09-17',
        '2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04', '2025-10-05', '2025-10-06', '2025-10-07',
        # 2026年
        '2026-01-01', '2026-01-26', '2026-01-27', '2026-01-28', '2026-01-29', '2026-01-30', '2026-01-31',
        '2026-02-01', '2026-02-02',
        '2026-04-04', '2026-04-05', '2026-04-06',
        '2026-05-01', '2026-05-02', '2026-05-03',
        '2026-06-19', '2026-06-20',
        '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07',
    ]
    holiday_dates = set(datetime.strptime(h, '%Y-%m-%d').date() for h in holidays)
    
    # 生成交易日列表
    trade_dates = []
    current = start_date
    while current <= end_date:
        # 排除周末 (5=周六, 6=周日)
        if current.weekday() < 5 and current.date() not in holiday_dates:
            trade_dates.append(current.date())
        current += timedelta(days=1)
    
    # 创建DataFrame
    df = pd.DataFrame({'trade_date': trade_dates})
    _trade_calendar_cache = df
    print(f"交易日历已缓存，共 {len(df)} 条记录")
    return df


def is_trading_day():
    """判断今天是否为A股交易日"""
    from datetime import datetime, date
    
    today = datetime.now()
    today_date = date.today()
    weekday = today.weekday()  # 0=周一, 6=周日
    
    # 周末不是交易日
    if weekday >= 5:
        print(f"今天({today.strftime('%Y-%m-%d')} 星期{weekday+1})是周末，不是交易日")
        return False
    
    try:
        # 从全局缓存获取交易日历
        df = _get_trade_calendar()
        
        # 直接判断今天是否在交易日历中
        if today_date in df['trade_date'].values:
            return True
        else:
            # 今天不在交易日中，可能是节假日
            print(f"今天({today.strftime('%Y-%m-%d')} 星期{weekday+1})不是A股交易日")
            return False
    except Exception as e:
        print(f"获取交易日历失败: {e}")
        # 如果获取失败，检查是否是周末
        return weekday < 5


def get_next_trading_day():
    """获取下一个交易日"""
    from datetime import datetime, timedelta, date
    
    today = datetime.now()
    
    try:
        # 从全局缓存获取完整交易日历（不过滤，用于查找未来交易日）
        df = _get_trade_calendar()
        trade_dates = df['trade_date'].tolist()
        
        # 从明天开始往后找（最多查15天）
        for i in range(1, 15):
            next_day = today + timedelta(days=i)
            next_day_date = date(next_day.year, next_day.month, next_day.day)
            if next_day_date in trade_dates:
                weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
                return next_day.strftime('%Y-%m-%d'), weekday_names[next_day.weekday()]
    except Exception as e:
        print(f"获取下一交易日失败: {e}")
    
    # 回退方案：找下一个工作日
    for i in range(1, 8):
        next_day = today + timedelta(days=i)
        if next_day.weekday() < 5:
            weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
            return next_day.strftime('%Y-%m-%d'), weekday_names[next_day.weekday()]
    
    return None, None


# ============== 多数据源函数 ==============

def _get_stock_data_sina(stock_code, days=120):
    """数据源1: 新浪财经API"""
    try:
        if stock_code.startswith('6'):
            sina_code = f"sh{stock_code}"
        else:
            sina_code = f"sz{stock_code}"
        
        url = f"https://hq.sinajs.cn/list={sina_code}"
        headers = {
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, f"新浪API HTTP {response.status_code}"
        
        content = response.text
        if not content or 'hq_str_' not in content:
            return None, "新浪API返回数据为空"
        
        import re
        import json
        import pandas as pd
        
        # 获取历史K线数据
        hist_url = f"https://finance.sina.com.cn/realstock/company/{sina_code}/hisdata/klc_kl.js?d=2025"
        hist_response = requests.get(hist_url, headers=headers, timeout=10)
        
        if hist_response.status_code == 200 and 'klines' in hist_response.text:
            match = re.search(r'klines\s*=\s*\[(.*?)\]', hist_response.text)
            if match:
                klines_str = match.group(1).replace('"', '"').replace("'", '"')
                klines = json.loads(f"[{klines_str}]")
                
                data = []
                for kline in klines:
                    parts = kline.split(',')
                    if len(parts) >= 6:
                        data.append({
                            'date': parts[0],
                            'open': float(parts[1]),
                            'close': float(parts[2]),
                            'high': float(parts[3]),
                            'low': float(parts[4]),
                            'volume': float(parts[5])
                        })
                
                if data:
                    df = pd.DataFrame(data)
                    return df, None
        
        # 回退: 使用实时数据
        var_name = f"hq_str_{sina_code}"
        start = content.find(var_name) + len(var_name) + 3
        end = content.find('";', start)
        
        if start > 2 and end > start:
            data_str = content[start:end]
            fields = data_str.split(',')
            
            if len(fields) >= 6:
                current_price = float(fields[1]) if fields[1] else 0
                open_price = float(fields[2]) if fields[2] else 0
                high_price = float(fields[3]) if fields[3] else 0
                low_price = float(fields[4]) if fields[4] else 0
                volume = float(fields[5]) if fields[5] else 0
                
                today = datetime.now().strftime('%Y-%m-%d')
                df = pd.DataFrame([{
                    'date': today,
                    'open': open_price,
                    'close': current_price,
                    'high': high_price,
                    'low': low_price,
                    'volume': volume
                }])
                return df, None
        
        return None, "新浪API无有效数据"
        
    except Exception as e:
        return None, f"新浪API异常: {e}"


def _get_stock_data_eastmoney(stock_code, days=120):
    """数据源2: 东方财富网站"""
    try:
        if stock_code.startswith('6'):
            em_code = f"1.{stock_code}"
        else:
            em_code = f"0.{stock_code}"
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
        
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',
            'fqt': '0',
            'secid': em_code,
            'beg': start_date,
            'end': end_date,
            'lmt': days
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://quote.eastmoney.com/'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            return None, f"东方财富HTTP {response.status_code}"
        
        data = response.json()
        if data.get('data') is None or 'klines' not in data['data']:
            return None, "东方财富返回数据为空"
        
        klines = data['data']['klines']
        if not klines:
            return None, "东方财富无K线数据"
        
        import pandas as pd
        records = []
        for kline in klines:
            parts = kline.split(',')
            if len(parts) >= 6:
                records.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': float(parts[5])
                })
        
        if not records:
            return None, "东方财富K线为空"
        
        df = pd.DataFrame(records)
        return df, None
        
    except Exception as e:
        return None, f"东方财富异常: {e}"


def _get_stock_data_tencent(stock_code, days=120):
    """数据源3: 腾讯财经API"""
    try:
        if stock_code.startswith('6'):
            tencent_code = f"sh{stock_code}"
        else:
            tencent_code = f"sz{stock_code}"
        
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            '_var': 'kline_dayqfq',
            'param': f"{tencent_code},day,,,{days},qfq"
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.qq.com/'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, f"腾讯API HTTP {response.status_code}"
        
        import re
        import json
        
        text = response.text
        match = re.search(r'kline_dayqfq\s*=\s*(.+)', text)
        if not match:
            return None, "腾讯API数据解析失败"
        
        data = json.loads(match.group(1))
        
        if tencent_code not in data.get('data', {}):
            return None, "腾讯API无该股票数据"
        
        stock_data = data['data'][tencent_code]
        # 先尝试qfqday，再尝试day
        klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
        if not klines:
            return None, "腾讯API无K线数据"
        
        import pandas as pd
        records = []
        for kline in klines:
            if len(kline) >= 5:
                records.append({
                    'date': kline[0],
                    'open': float(kline[1]),
                    'close': float(kline[2]),
                    'high': float(kline[3]),
                    'low': float(kline[4]),
                    'volume': float(kline[5]) if len(kline) > 5 else 0
                })
        
        if not records:
            return None, "腾讯API K线为空"
        
        df = pd.DataFrame(records)
        return df, None
        
    except Exception as e:
        return None, f"腾讯API异常: {e}"


def _get_stock_data_akshare(stock_code, days=120):
    """数据源4 (最终回退): akshare"""
    try:
        import akshare as ak
        
        # 如果是ETF，使用ETF专用接口
        if is_etf(stock_code):
            print(f"    检测到ETF，尝试获取ETF数据...")
            try:
                # 尝试使用ETF基金接口
                df = ak.fund_etf_hist_em(symbol=stock_code, period="daily", 
                                         start_date="20260101", end_date="20260302", adjust="")
                if df is not None and not df.empty:
                    print(f"    ✓ ETF数据获取成功 (fund_etf_hist_em)")
                    import pandas as pd
                    column_map = {
                        '日期': 'date', '开盘': 'open', '收盘': 'close', 
                        '最高': 'high', '最低': 'low', '成交量': 'volume'
                    }
                    rename_cols = {k: v for k, v in column_map.items() if k in df.columns}
                    df = df.rename(columns=rename_cols)
                    df = df.sort_values('date').reset_index(drop=True)
                    return df.tail(days), None
            except Exception as e:
                print(f"    ✗ ETF接口失败: {e}")
                # ETF 获取失败，返回特定错误让它跳过
                return None, "ETF数据不可用(可跳过)"
        
        # 普通股票使用A股接口
        df = ak.stock_zh_a_hist(
            symbol=stock_code, 
            period="daily", 
            start_date="20260101", 
            end_date="20260302",
            adjust=""
        )
        
        if df is None or df.empty:
            return None, "AKShare返回空数据"
        
        import pandas as pd
        column_map = {
            '日期': 'date', '开盘': 'open', '收盘': 'close', 
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_change',
            '涨跌额': 'change', '换手率': 'turnover'
        }
        
        rename_cols = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename_cols)
        df = df.sort_values('date').reset_index(drop=True)
        
        return df.tail(days), None
        
    except Exception as e:
        return None, f"AKShare异常: {e}"
def _normalize_dataframe(df):
    """标准化DataFrame格式"""
    import pandas as pd
    
    if df is None or len(df) == 0:
        return None
    
    col_mapping = {
        '日期': 'date', '开盘': 'open', '收盘': 'close',
        '最高': 'high', '最低': 'low', '成交量': 'volume'
    }
    
    df = df.rename(columns=col_mapping)
    
    required_cols = ['date', 'open', 'close', 'high', 'low', 'volume']
    available_cols = [c for c in required_cols if c in df.columns]
    df = df[available_cols].copy()
    
    for col in ['open', 'close', 'high', 'low', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna()
    
    if len(df) == 0:
        return None
    
    df = df.sort_values('date').reset_index(drop=True)
    return df


def get_stock_data(stock_code, days=120):
    """获取股票数据 - 多数据源回退: 新浪 → 东方财富 → 腾讯 → AKShare"""
    
    print(f"  正在获取 {stock_code} 数据...")
    
    sources = [
        ("腾讯财经", _get_stock_data_tencent),
        ("AKShare", _get_stock_data_akshare),
        ("东方财富", _get_stock_data_eastmoney),
        ("新浪财经", _get_stock_data_sina)
    ]
    
    last_error = None
    
    for source_name, source_func in sources:
        print(f"    尝试 {source_name}...")
        df, error = source_func(stock_code, days)
        
        if error:
            print(f"    ✗ {source_name} 失败: {error}")
            last_error = error
            time.sleep(0.5)
            continue
        
        df = _normalize_dataframe(df)
        
        if df is not None and len(df) > 0:
            print(f"    ✓ {source_name} 成功，获取 {len(df)} 条数据")
            # 检查是否满足技术指标计算的最低要求 (至少20天)
            if len(df) >= 20:
                return df.tail(days)
            else:
                # 数据不足，尝试下一个数据源
                print(f"    ⚠ {source_name} 数据不足 ({len(df)}条)，需要至少20条，继续尝试...")
                last_error = f"{source_name} 数据不足 ({len(df)}条)"
                time.sleep(0.5)
                continue
        else:
            print(f"    ✗ {source_name} 数据无效")
            last_error = f"{source_name} 返回空数据"
    
    print(f"  ❌ 所有数据源均失败: {last_error}")
    return None


def calculate_indicators(df):
    """计算技术指标 - A股常用参数"""
    import numpy as np
    
    if df is None or len(df) < 20:
        return None
    
    close = df['close'].astype(float).values
    high = df['high'].astype(float).values
    low = df['low'].astype(float).values
    volume = df['volume'].astype(float).values
    open_price = df['open'].astype(float).values
    
    indicators = {}
    
    # MA均线 (5,10,20,60)
    indicators['MA5'] = np.mean(close[-5:])
    indicators['MA10'] = np.mean(close[-10:])
    indicators['MA20'] = np.mean(close[-20:])
    indicators['MA60'] = np.mean(close[-60:]) if len(close) >= 60 else np.mean(close[-30:])
    
    # MACD (A股常用参数: 10,20,7)
    ema10 = close.copy()
    ema20 = close.copy()
    for i in range(1, len(close)):
        ema10[i] = ema10[i-1] * (1-2/(10+1)) + close[i] * (2/(10+1))
        ema20[i] = ema20[i-1] * (1-2/(20+1)) + close[i] * (2/(20+1))
    
    macd = ema10 - ema20
    signal = np.convolve(macd, np.ones(7)/7, mode='same')
    hist = macd - signal
    
    indicators['MACD'] = macd[-1]
    indicators['MACD_signal'] = signal[-1]
    indicators['MACD_hist'] = hist[-1]
    
    # KDJ (9日)
    lowest_low = np.min(low[-9:])
    highest_high = np.max(high[-9:])
    
    if highest_high - lowest_low == 0:
        rsv = 50
    else:
        rsv = (close[-1] - lowest_low) / (highest_high - lowest_low) * 100
    
    k = 2/3 * 50 + 1/3 * rsv
    d = 2/3 * 50 + 1/3 * k
    j = 3 * k - 2 * d
    
    indicators['KDJ_K'] = k
    indicators['KDJ_D'] = d
    indicators['KDJ_J'] = j
    
    # RSI (14日)
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    
    avg_gain = np.mean(gain[-14:]) if len(gain) >= 14 else np.mean(gain)
    avg_loss = np.mean(loss[-14:]) if len(loss) >= 14 else np.mean(loss)
    
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    indicators['RSI'] = rsi
    
    # BOLL布林带 (20日)
    ma20 = np.mean(close[-20:])
    std20 = np.std(close[-20:])
    
    indicators['BOLL_UP'] = ma20 + 2 * std20
    indicators['BOLL_MID'] = ma20
    indicators['BOLL_LOW'] = ma20 - 2 * std20
    
    # OBV能量潮
    obv = 0
    for i in range(1, len(close)):
        if close[i] > close[i-1]:
            obv += volume[i]
        elif close[i] < close[i-1]:
            obv -= volume[i]
    indicators['OBV'] = obv
    
    # 量比
    vol_ma5 = np.mean(volume[-5:])
    indicators['VOL_RATIO'] = volume[-1] / vol_ma5 if vol_ma5 > 0 else 1
    
    # 最新价和涨跌
    indicators['CLOSE'] = close[-1]
    indicators['PREV_CLOSE'] = close[-2] if len(close) > 1 else close[-1]
    indicators['CHANGE'] = indicators['CLOSE'] - indicators['PREV_CLOSE']
    indicators['CHANGE_PCT'] = indicators['CHANGE'] / indicators['PREV_CLOSE'] * 100 if indicators['PREV_CLOSE'] != 0 else 0
    
    # 换手率
    indicators['TURNOVER'] = df['turnover'].iloc[-1] if 'turnover' in df.columns else 0
    
    # 委比 (简化估算)
    indicators['WILL_CHANGE'] = indicators['CHANGE_PCT']
    
    # 内外盘
    if close[-1] >= open_price[-1]:
        indicators['INNER_DISK'] = volume[-1] * 0.6
        indicators['OUTER_DISK'] = volume[-1] * 0.4
    else:
        indicators['INNER_DISK'] = volume[-1] * 0.4
        indicators['OUTER_DISK'] = volume[-1] * 0.6
    
    return indicators


def analyze_stock(stock):
    """分析单只股票"""
    code = stock['code']
    name = stock['name']
    print(f"正在分析 {name} ({code})...")
    
    # 获取2026年最新数据
    df = get_stock_data(code)
    if df is None or df.empty:
        # 如果是ETF，获取失败时打印友好消息
        if is_etf(code):
            print(f"  ⚠️ {name} (ETF) 暂无数据，跳过")
        else:
            print(f"  ⚠️ {name} 无数据")
        return None
    
    ind = calculate_indicators(df)
    if ind is None:
        return None
    
    # 计算买卖点信号
    signals = calculate_buy_sell_signals(df, ind)
    
    return {
        "name": stock['name'],
        "code": stock['code'],
        "indicators": ind,
        "signals": signals,
        "data_date": df['date'].iloc[-1] if len(df) > 0 else "N/A"
    }


def calculate_buy_sell_signals(df, indicators=None):
    """根据技术指标计算买卖点信号
    
    Args:
        df: 股票数据DataFrame
        indicators: 可选的预计算技术指标字典，如果提供则复用这些指标，避免重复计算
    """
    import numpy as np
    
    if df is None or len(df) < 20:
        return None
    
    # 如果提供了预计算的指标，直接使用
    if indicators is not None:
        ma5 = indicators.get('MA5', 0)
        ma20 = indicators.get('MA20', 0)
        j = indicators.get('KDJ_J', 0)
        rsi = indicators.get('RSI', 50)
        macd = indicators.get('MACD', 0)
    else:
        # 否则重新计算（向后兼容）
        # 重命名列
        df = df.rename(columns={'收盘': 'close', '最高': 'high', '最低': 'low'})
        
        close = df['close'].astype(float).values
        high = df['high'].astype(float).values
        low = df['low'].astype(float).values
        
        # 计算均线
        ma5 = np.mean(close[-5:])
        ma10 = np.mean(close[-10:])
        ma20 = np.mean(close[-20:])
        
        # 计算KDJ
        lowest_low = np.min(low[-9:])
        highest_high = np.max(high[-9:])
        if highest_high - lowest_low == 0:
            rsv = 50
        else:
            rsv = (close[-1] - lowest_low) / (highest_high - lowest_low) * 100
        k = 2/3 * 50 + 1/3 * rsv
        d = 2/3 * 50 + 1/3 * k
        j = 3 * k - 2 * d
        
        # 计算RSI
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.mean(gain[-14:])
        avg_loss = np.mean(loss[-14:])
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # 计算MACD
        ema12 = close.copy()
        ema20 = close.copy()
        for i in range(1, len(close)):
            ema12[i] = ema12[i-1] * (1-2/(10+1)) + close[i] * (2/(10+1))
            ema20[i] = ema20[i-1] * (1-2/(20+1)) + close[i] * (2/(20+1))
        macd = ema12[-1] - ema20[-1]
    
    signals = {}
    
    # 均线信号
    if ma5 > ma20:
        signals["ma_cross"] = "MA5>MA20 (上涨趋势)"
    else:
        signals["ma_cross"] = "MA5<MA20 (下跌趋势)"
    
    # KDJ信号
    # 当使用预计算指标时，需要从 indicators 获取 k 和 d 值
    if indicators is not None:
        k_val = indicators.get('KDJ_K', 50)
        d_val = indicators.get('KDJ_D', 50)
    else:
        k_val = k
        d_val = d
    
    if j > 100:
        signals["kdj"] = "J={:.1f} 超买".format(j)
    elif j < 0:
        signals["kdj"] = "J={:.1f} 超卖".format(j)
    else:
        signals["kdj"] = "K={:.1f} D={:.1f}".format(k_val, d_val)
    
    # RSI信号
    if rsi > 70:
        signals["rsi"] = "RSI={:.1f} 超买".format(rsi)
    elif rsi < 30:
        signals["rsi"] = "RSI={:.1f} 超卖".format(rsi)
    else:
        signals["rsi"] = "RSI={:.1f} 中性".format(rsi)
    
    # MACD信号
    if macd > 0:
        signals["macd"] = "MACD>0 金叉"
    else:
        signals["macd"] = "MACD<0 死叉"
    
    # 综合建议
    buy_score = 0
    sell_score = 0
    
    if ma5 > ma20:
        buy_score += 1
    else:
        sell_score += 1
    
    if j < 0:
        buy_score += 2
    elif j > 100:
        sell_score += 2
    
    if rsi < 30:
        buy_score += 2
    elif rsi > 70:
        sell_score += 2
    
    if macd > 0:
        buy_score += 1
    else:
        sell_score += 1
    
    if buy_score >= 4:
        signals["recommendation"] = "🟢 强烈买入"
    elif buy_score >= 2:
        signals["recommendation"] = "🟡 关注买入"
    elif sell_score >= 4:
        signals["recommendation"] = "🔴 强烈卖出"
    elif sell_score >= 2:
        signals["recommendation"] = "🟠 警惕回调"
    else:
        signals["recommendation"] = "➡️ 观望"
    
    return signals


def calculate_score_1_5(indicators, signals):
    """计算1-5分评分系统 (Ashare-AI-Strategy-Analyst风格)
    
    基于买入/卖出信号数量计算评分：
    - 5分: 强烈看涨
    - 4分: 看涨
    - 3分: 偏多
    - 2分: 中性
    - 1分: 看跌
    
    Args:
        indicators: 技术指标字典
        signals: 买卖信号字典
    """
    if indicators is None or signals is None:
        return 2, "数据不足"
    
    buy_signals = []
    sell_signals = []
    
    # 从 signals 中统计买入/卖出信号关键词
    signal_text = str(signals.values())
    
    # 买入信号关键词
    buy_keywords = ['上涨', '反弹', '金叉', '超卖', '买入', '看涨', '突破']
    for kw in buy_keywords:
        if kw in signal_text:
            buy_signals.append(kw)
    
    # 卖出信号关键词  
    sell_keywords = ['下跌', '回调', '死叉', '超买', '卖出', '看跌', '跌破']
    for kw in sell_keywords:
        if kw in signal_text:
            sell_signals.append(kw)
    
    # 基于指标额外判断
    try:
        # MACD 金叉/死叉
        macd_hist = indicators.get('MACD_hist', 0)
        if macd_hist > 0:
            buy_signals.append('MACD金叉')
        elif macd_hist < 0:
            sell_signals.append('MACD死叉')
        
        # KDJ 超卖/超买
        kdj_j = indicators.get('KDJ_J', 50)
        if kdj_j < 0:
            buy_signals.append('KDJ超卖')
        elif kdj_j > 100:
            sell_signals.append('KDJ超买')
        
        # RSI 超卖/超买
        rsi = indicators.get('RSI', 50)
        if rsi < 30:
            buy_signals.append('RSI超卖')
        elif rsi > 70:
            sell_signals.append('RSI超买')
        
        # 均线趋势
        ma5 = indicators.get('MA5', 0)
        ma20 = indicators.get('MA20', 0)
        if ma5 > ma20:
            buy_signals.append('MA多头')
        elif ma5 < ma20:
            sell_signals.append('MA空头')
            
    except Exception:
        pass
    
    # 计算评分
    buy_count = len(buy_signals)
    sell_count = len(sell_signals)
    total = buy_count + sell_count
    
    if total == 0:
        return 2, "中性"
    
    if buy_count > sell_count:
        # 看涨: 3-5分
        score = 3 + (buy_count / total) * 2
        score = min(5, max(3, round(score)))
        signal = "🟢 看涨"
    elif sell_count > buy_count:
        # 看跌: 1-2分
        score = 3 - (sell_count / total) * 2
        score = min(2, max(1, round(score)))
        signal = "🔴 看跌"
    else:
        # 中性
        score = 2
        signal = "🟡 中性"
    
    # 详细说明
    detail = f"买入信号{buy_count}个" if buy_count > 0 else ""
    if detail and sell_count > 0:
        detail += ", "
    if sell_count > 0:
        detail += f"卖出信号{sell_count}个"
    
    return score, signal, detail


def generate_stock_chart(stock_code, stock_name):
    """生成A股股票3个月走势图（使用腾讯财经数据）"""
    try:
        import requests
        import pandas as pd
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from datetime import datetime, timedelta
        
        # 使用腾讯财经API获取数据
        if stock_code.startswith('6'):
            tencent_code = f"sh{stock_code}"
        else:
            tencent_code = f"sz{stock_code}"
        
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {'_var': 'kline_dayqfq', 'param': f"{tencent_code},day,,,120,qfqa"}
        
        response = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if response.status_code != 200:
            return None
        
        import re, json
        match = re.search(r'kline_dayqfq\s*=\s*(.+)', response.text)
        if not match:
            return None
        
        data = json.loads(match.group(1))
        stock_data = data.get('data', {}).get(tencent_code, {})
        klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
        
        if not klines or len(klines) < 10:
            return None
        
        # 转换为DataFrame
        records = []
        for k in klines:
            if len(k) >= 5:
                records.append({
                    'date': k[0],
                    'open': float(k[1]),
                    'close': float(k[2]),
                    'high': float(k[3]),
                    'low': float(k[4])
                })
        
        df = pd.DataFrame(records)
        if len(df) < 10:
            return None
        
        df = df.tail(60)
        df = df.tail(60)
        
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(range(len(df)), df['close'].astype(float), 'b-', linewidth=1.5, label='Close')
        
        close = df['close'].astype(float)
        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()
        
        ax.plot(range(len(ma5)), ma5, 'r--', linewidth=1, alpha=0.7, label='MA5')
        ax.plot(range(len(ma10)), ma10, 'g--', linewidth=1, alpha=0.7, label='MA10')
        
        latest_price = close.iloc[-1]
        ax.annotate(f'{latest_price:.2f}', 
                   xy=(len(df)-1, latest_price),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=10, fontweight='bold', color='red')
        
        ax.set_title(f'{stock_code} - 3 Month Trend', fontsize=12, fontweight='bold')
        ax.set_ylabel('Price (CNY)')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        chart_path = f'/home/zhiping/.openclaw/workspace/reports/{stock_code}_chart.png'
        plt.savefig(chart_path, dpi=80, bbox_inches='tight')
        plt.close()
        
        return chart_path
        
    except Exception as e:
        print(f"  生成走势图失败: {e}")
        return None


def generate_report(stock_analyses, delay_reason=""):
    """生成 HTML 报告
    
    Args:
        stock_analyses: 股票分析数据
        delay_reason: 延迟发送的原因（可选）
    """
    
    # 添加延迟说明
    delay_note = ""
    if delay_reason:
        delay_note = f"""
    <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
        <p style="margin: 0; color: #856404; font-size: 14px;">
            <strong>⚠️ 抱歉通知：</strong>今日报告未能按时（9:00）发送。<br>
            原因：{delay_reason}<br>
            为您带来的不便，深表歉意！
        </p>
    </div>
"""
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 100%; margin: 0 auto; padding: 10px; background: #f5f5f5; }}
        .card {{ background: white; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 100%; box-sizing: border-box; overflow-x: auto; }}
        .stock-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-bottom: 10px; }}
        .stock-name {{ font-size: 20px; font-weight: bold; color: #333; }}
        .stock-code {{ color: #666; font-size: 12px; }}
        .price {{ font-size: 20px; font-weight: bold; }}
        .price-up {{ color: #e74c3c; }}
        .price-down {{ color: #27ae60; }}
        .change {{ font-size: 14px; padding: 3px 8px; border-radius: 4px; }}
        .change-up {{ background: #fde8e8; color: #e74c3c; }}
        .change-down {{ background: #e8f5e9; color: #27ae60; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 5px; text-align: left; border-bottom: 1px solid #eee; font-size: 12px; }}
        th {{ color: #666; font-weight: 500; font-size: 11px; }}
        .section-title {{ font-size: 16px; font-weight: 600; color: #333; margin: 15px 0 10px; }}
        .tag {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; margin-right: 5px; }}
        .tag-red {{ background: #ffebee; color: #c62828; }}
        .tag-green {{ background: #e8f5e9; color: #2e7d32; }}
        .tag-yellow {{ background: #fff8e1; color: #f57f17; }}
        .summary {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
        .summary-item {{ text-align: center; padding: 10px; background: #f8f9fa; border-radius: 8px; }}
        .summary-value {{ font-size: 16px; font-weight: bold; color: #333; }}
        .summary-label {{ font-size: 11px; color: #666; margin-top: 3px; }}
    </style>
</head>
<body>
    {delay_note}
    <h1 style="text-align: center; color: #333;">📈 A股每日观察</h1>
    <p style="text-align: center; color: #666; margin-bottom: 30px;">数据更新日期: """
    
    html += datetime.now().strftime("%Y-%m-%d %H:%M")
    html += """</p>
    <p style="text-align: center; color: #999; font-size: 12px; margin-top: -20px;">数据来源: 腾讯财经</p>
"""
    
    for analysis in stock_analyses:
        if analysis is None:
            continue
        
        
        ind = analysis['indicators']
        change_pct = ind.get('CHANGE_PCT', 0)
        
        # 计算1-5评分
        stock_signals = analysis.get('signals', {})
        score, score_signal, score_detail = calculate_score_1_5(ind, stock_signals)
        
        # 判断趋势
        if ind['MA5'] > ind['MA20']:
            trend = "📈 上涨"
        elif ind['MA5'] < ind['MA20']:
            trend = "📉 下跌"
        else:
            trend = "➡️ 震荡"
        
        volume_status = "放量" if ind['VOL_RATIO'] > 1.5 else "缩量" if ind['VOL_RATIO'] < 0.8 else "正常"
        
        # KDJ 信号
        if ind['KDJ_J'] > 100:
            kdj_signal = '<span class="tag tag-red">超买</span>'
        elif ind['KDJ_J'] < 0:
            kdj_signal = '<span class="tag tag-green">超卖</span>'
        else:
            kdj_signal = '<span class="tag tag-yellow">中性</span>'
        
        # RSI 信号
        if ind['RSI'] > 70:
            rsi_signal = '<span class="tag tag-red">超买</span>'
        elif ind['RSI'] < 30:
            rsi_signal = '<span class="tag tag-green">超卖</span>'
        else:
            rsi_signal = '<span class="tag tag-yellow">中性</span>'
        
        # MACD 信号
        if ind['MACD_hist'] > 0:
            macd_signal = '<span class="tag tag-green">金叉</span>'
        elif ind['MACD_hist'] < 0:
            macd_signal = '<span class="tag tag-red">死叉</span>'
        else:
            macd_signal = '<span class="tag tag-yellow">震荡</span>'
        
        # BOLL 信号
        if ind['CLOSE'] > ind['BOLL_UP']:
            boll_signal = "突破上轨"
        elif ind['CLOSE'] < ind['BOLL_LOW']:
            boll_signal = "跌破下轨"
        else:
            boll_signal = "中轨运行"
        
        price_class = "price-up" if change_pct > 0 else "price-down"
        change_class = "change-up" if change_pct > 0 else "change-down"
        change_symbol = "+" if change_pct > 0 else ""
        
        html += f"""
    <div class="card">
        <div class="stock-header">
            <div>
                <div class="stock-name">{analysis['name']}</div>
                <div class="stock-code">{analysis['code']} | 数据日期: {analysis['data_date']}</div>
                <div style="margin-top: 8px;">
                    <span style="display: inline-block; padding: 5px 12px; border-radius: 6px; font-size: 16px; font-weight: bold; background: {'#4caf50' if score >= 4 else '#8bc34a' if score == 3 else '#ff9800' if score == 2 else '#f44336'}; color: white;">
                        {score}分 {score_signal}
                    </span>
                    <span style="color: #666; font-size: 12px; margin-left: 8px;">{score_detail}</span>
                </div>
            </div>
            <div style="text-align: right;">
                <div class="price {price_class}">¥{ind['CLOSE']:.2f}</div>
                <span class="change {change_class}">{change_symbol}{change_pct:.2f}%</span>
            </div>
        </div>
        
        <div class="summary">
            <div class="summary-item">
                <div class="summary-value">{trend}</div>
                <div class="summary-label">均线趋势</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{volume_status}</div>
                <div class="summary-label">量比 ({ind['VOL_RATIO']:.2f})</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{ind['TURNOVER']:.2f}%</div>
                <div class="summary-label">换手率</div>
            </div>
        </div>
        
        <div class="section-title">📊 技术指标 (A股参数)</div>
        <table>
            <tr><th>指标</th><th>数值</th><th>信号</th></tr>
            <tr><td>MA(5,10,20,60)</td><td>{ind['MA5']:.2f} / {ind['MA10']:.2f} / {ind['MA20']:.2f} / {ind['MA60']:.2f}</td><td>{trend}</td></tr>
            <tr><td>MACD (10,20,7)</td><td>{ind['MACD']:.4f} / {ind['MACD_signal']:.4f}</td><td>{macd_signal}</td></tr>
            <tr><td>KDJ (9日)</td><td>K={ind['KDJ_K']:.1f} D={ind['KDJ_D']:.1f} J={ind['KDJ_J']:.1f}</td><td>{kdj_signal}</td></tr>
            <tr><td>RSI(14)</td><td>{ind['RSI']:.1f}</td><td>{rsi_signal}</td></tr>
            <tr><td>BOLL (20日)</td><td>{ind['BOLL_LOW']:.2f} ~ {ind['BOLL_MID']:.2f} ~ {ind['BOLL_UP']:.2f}</td><td>{boll_signal}</td></tr>
            <tr><td>OBV</td><td>{ind['OBV']:,.0f}</td><td>{"上涨" if ind['OBV'] > 0 else "下跌"}</td></tr>
        </table>
        
        <div class="section-title">📦 交易活跃度</div>
        <table>
            <tr><th>指标</th><th>数值</th><th>说明</th></tr>
            <tr><td>量比</td><td>{ind['VOL_RATIO']:.2f}</td><td>{"明显放量" if ind['VOL_RATIO'] > 2.5 else "温和放量" if ind['VOL_RATIO'] > 1.5 else "正常" if ind['VOL_RATIO'] > 0.8 else "缩量"}</td></tr>
            <tr><td>换手率</td><td>{ind['TURNOVER']:.2f}%</td><td>{"高活跃" if ind['TURNOVER'] > 5 else "正常" if ind['TURNOVER'] > 3 else "低活跃"}</td></tr>
            <tr><td>内盘/外盘</td><td>{ind['INNER_DISK']:,.0f} / {ind['OUTER_DISK']:,.0f}</td><td>{"多方占优" if ind['INNER_DISK'] > ind['OUTER_DISK'] else "空方占优"}</td></tr>
        </table>
        
        <!-- 买卖点信号 -->
        <div class="section-title">🎯 买卖点建议</div>
"""
    
        # 添加买卖点数据（如果存在）
        try:
            signals_data = analysis.get('signals')
            if signals_data is not None:
                html += f"""
            <table>
                <tr><th>指标</th><th>信号</th></tr>
                <tr><td>均线趋势</td><td>{analysis['signals'].get('ma_cross', 'N/A')}</td></tr>
                <tr><td>KDJ</td><td>{analysis['signals'].get('kdj', 'N/A')}</td></tr>
                <tr><td>RSI</td><td>{analysis['signals'].get('rsi', 'N/A')}</td></tr>
                <tr><td>MACD</td><td>{analysis['signals'].get('macd', 'N/A')}</td></tr>
                <tr><td><strong>综合建议</strong></td><td><strong style="font-size:16px;">{analysis['signals'].get('recommendation', 'N/A')}</strong></td></tr>
            </table>
"""
            else:
                html += """        <p style="color: #999; font-style: italic;">数据不足30条，无法计算买卖点！</p>
"""
        except Exception as e:
            html += f"""        <p style="color: red;">错误: {e}</p>
"""
        
        # 添加走势图
        html += f"""        <!-- CHART_{analysis['code']} -->
    </div>
"""
    
    # 添加下一交易日提示
    next_date, next_weekday = get_next_trading_day()
    if next_date and next_weekday:
        html += f"""
    <div style="text-align: center; margin-top: 20px; padding: 15px; background: #e3f2fd; border-radius: 8px;">
        <p style="margin: 0; color: #1565c0; font-size: 14px;">
            📅 <strong>下一交易日：</strong>{next_date} ({next_weekday})
        </p>
    </div>
"""
    
    html += """
    <p style="text-align: center; color: #999; font-size: 12px; margin-top: 30px;">
        由 OpenClaw 自动生成 | 数据来源: 腾讯财经
    </p>
    
    <!-- 1-5分评分说明 -->
    <div style="background: #f5f5f5; border-radius: 8px; padding: 15px; margin: 20px auto; max-width: 600px;">
        <h4 style="margin: 0 0 10px 0; color: #333; font-size: 14px;">📊 1-5分评分说明</h4>
        <table style="width: 100%; font-size: 12px; color: #666;">
            <tr>
                <td style="padding: 3px 0;"><span style="background: #4caf50; color: white; padding: 2px 8px; border-radius: 4px;">5分</span> 强烈看涨</td>
                <td style="padding: 3px 0;"><span style="background: #8bc34a; color: white; padding: 2px 8px; border-radius: 4px;">4分</span> 看涨</td>
                <td style="padding: 3px 0;"><span style="background: #ff9800; color: white; padding: 2px 8px; border-radius: 4px;">2分</span> 中性</td>
                <td style="padding: 3px 0;"><span style="background: #f44336; color: white; padding: 2px 8px; border-radius: 4px;">1分</span> 看跌</td>
            </tr>
        </table>
        <p style="font-size: 11px; color: #999; margin: 8px 0 0 0;">
            评分基于MACD/KDJ/RSI/均线等技术指标的买入/卖出信号数量计算
        </p>
    </div>
</body>
</html>
"""
    
    return html


def send_email(html_report, subject_prefix="", skip_charts=False):
    """发送邮件 - 先用tencent-exmail，失败则用Gmail"""
    # 生成各股票走势图
    print("生成股票走势图...")
    stock_codes = [s["code"] for s in STOCKS]
    stock_names = [s["name"] for s in STOCKS]
    chart_paths = {}
    
    # 始终生成图表
    for code, name in zip(stock_codes, stock_names):
        chart_path = generate_stock_chart(code, name)
        if chart_path:
            chart_paths[code] = chart_path
            print(f"  ✅ {name} 走势图已生成")
    
    # 添加走势图图片到HTML (嵌入base64)
    if chart_paths:
        for code, chart_path in chart_paths.items():
            try:
                import base64
                with open(chart_path, 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode()
                    img_tag = f'<img src="data:image/png;base64,{img_data}" style="width:100%; margin-top:15px; border-radius:8px;">'
                    placeholder = f'<!-- CHART_{code} -->'
                    print(f"  Replacing '{placeholder}' in HTML...")
                    html_report = html_report.replace(placeholder, img_tag)
            except Exception as e:
                print(f"  添加图片失败: {e}")
    
    subject = f"{subject_prefix}A股每日观察 - {datetime.now().strftime('%Y-%m-%d')}"
    
    # 方法1: 尝试用 tencent-exmail (QQ邮箱 SMTP)
    print("尝试使用 tencent-exmail (QQ邮箱) 发送...")
    if send_via_qq_smtp(html_report, subject):
        print("✅ 邮件发送成功 (QQ邮箱)!")
        return html_report
    
    # 方法2: 回退到 Gmail
    print("QQ邮箱发送失败，尝试使用 Gmail...")
    send_via_gmail(html_report, subject_prefix, chart_paths)
    return html_report


def send_via_qq_smtp(html_report, subject):
    """通过 QQ邮箱 SMTP 发送"""
    import smtplib
    from email.mime.multipart import MIMEMultipart

    from email.mime.text import MIMEText
    from email.mime.image import MIMEImage
    
    qq_email = "9892890@qq.com"
    qq_password = "dqwervcgpylbbgcg"  # QQ邮箱 SMTP 授权码
    
    msg = MIMEMultipart('alternative')
    msg['From'] = qq_email
    msg['To'] = ", ".join(RECIPIENTS)
    msg['Subject'] = subject
    msg.attach(MIMEText(html_report, 'html'))
    
    try:
        # QQ邮箱 SMTP: smtp.qq.com, 端口 587 (STARTTLS)
        server = smtplib.SMTP("smtp.qq.com", 587)
        server.starttls()
        server.login(qq_email, qq_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"  QQ邮箱发送失败: {e}")
        return False


def send_via_gmail(html_report, subject_prefix="", chart_paths=None):
    """通过 Gmail SMTP 发送"""
    import smtplib
    from email.mime.multipart import MIMEMultipart

    from email.mime.text import MIMEText
    from email.mime.image import MIMEImage
    
    smtp_password = os.environ.get("GMAIL_SMTP_PASSWORD")
    if not smtp_password:
        print("❌ 未设置 GMAIL_SMTP_PASSWORD")
        return False
    
    subject = f"{subject_prefix}A股每日观察 - {datetime.now().strftime('%Y-%m-%d')}"
    
    msg = MIMEMultipart('alternative')
    msg['From'] = GMAIL_SENDER_EMAIL
    msg['To'] = ", ".join(RECIPIENTS)
    msg['Subject'] = subject
    msg.attach(MIMEText(html_report, 'html'))
    
    # 添加图片附件 (使用股票代码作为Content-ID)
    if chart_paths:
        for code, chart_path in chart_paths.items():
            try:
                with open(chart_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', f'<{code}_chart>')
                    msg.attach(img)
            except Exception as e:
                print(f"  添加图片失败: {e}")
    
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_SENDER_EMAIL, smtp_password)
            server.send_message(msg)
        print("✅ 邮件发送成功 (Gmail)!")
        return True
    except Exception as e:
        print(f"❌ Gmail发送失败: {e}")
        return False


def main(is_test=False, delay_reason=""):
    print(f"开始获取 A股数据... ({datetime.now()})")
    print("使用 AKShare 获取2026年最新数据...")
    
    # 不使用代理，直接获取数据
    print("开始获取数据...")
    
    analyses = []
    errors = []  # 记录收集过程中的错误
    for stock in STOCKS:
        try:
            analysis = analyze_stock(stock)
            if analysis:
                analyses.append(analysis)
            else:
                # 记录无数据的情况
                errors.append(f"{stock['name']}({stock['code']}): 无数据")
        except Exception as e:
            errors.append(f"{stock['name']}({stock['code']}): {str(e)}")
    
    # 检查是否需要延迟发送报告
    current_time = datetime.now()
    time_limit = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
    
    # 如果没有传入延迟原因，自动检测
    if not delay_reason:
        delay_reasons = []
        
        # 检查是否超过9:30
        if current_time > time_limit:
            delay_reasons.append(f"当前时间 {current_time.strftime('%H:%M')} 已超过9:30收盘时报送")
        
        # 检查是否有错误
        if errors:
            error_details = "; ".join(errors[:5])  # 限制显示前5个错误
            if len(errors) > 5:
                error_details += f" 等共{len(errors)}个问题"
            delay_reasons.append(f"数据收集中出现{len(errors)}个问题: {error_details}")
        
        if delay_reasons:
            delay_reason = " | ".join(delay_reasons)
    
    if not analyses:
        print("❌ 没有获取到任何数据")
        return
    
    # 生成报告（带延迟说明）
    html_report = generate_report(analyses, delay_reason)
    
    # 发送邮件
    subject_prefix = "【测试】" if is_test else ""
    if delay_reason:
        subject_prefix = "【延迟发送】" + subject_prefix
    html_report = send_email(html_report, subject_prefix, skip_charts=is_test)
    
    # 保存到文件
    report_dir = Path("/home/zhiping/.openclaw/workspace/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"a_stock_daily_{datetime.now().strftime('%Y%m%d')}.html"
    with open(report_file, 'w') as f:
        f.write(html_report)
    print(f"报告已保存: {report_file}")


if __name__ == "__main__":
    is_test = "--test" in sys.argv
    
    # 解析延迟原因参数
    delay_reason = ""
    if "--delay" in sys.argv:
        idx = sys.argv.index("--delay")
        if idx + 1 < len(sys.argv):
            delay_reason = sys.argv[idx + 1]
    
    # 非测试模式：检查是否为A股交易日
    if not is_test:
        print("检查今天是否为A股交易日...")
        if not is_trading_day():
            print("今天不是A股交易日，程序退出")
            sys.exit(0)
    
    main(is_test, delay_reason)

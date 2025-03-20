import requests
import pandas as pd
import json
import time
from datetime import datetime, timedelta

# ================== 基础数据获取 ==================
def get_sohu_stock_data(code, start_date, end_date):
    """通过搜狐财经API获取股票历史数据"""
    url = "http://q.stock.sohu.com/hisHq"
    params = {
        "code": f"cn_{code}",
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "stat": "1",
        "order": "D",
        "period": "d"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()[0]['hq']
        
        df = pd.DataFrame(data, columns=[
            'date', 'open', 'close_price', 'change', 'pct_change',
            'low', 'high', 'volume', 'amount', 'turnover_rate'
        ])
        df['date'] = pd.to_datetime(df['date'])
        return df[['date', 'close_price']]
    
    except Exception as e:
        print(f"股票数据获取失败: {str(e)}")
        return pd.DataFrame()

# ================== PE数据获取（基于网页4爬虫方案优化） ==================
def get_hs300_pe_history(start_date, end_date):
    """获取沪深300历史PE数据（基于东方财富API）"""
    pe_data = []
    current_date = start_date
    
    while current_date <= end_date:
        url = "http://48.push2.eastmoney.com/api/qt/clist/get"
        params = (
            ('pn', '1'),
            ('pz', '1'),
            ('po', '1'),
            ('np', '2'),
            ('ut', 'bd1d9ddb04089700cf9c27f6f7426281'),
            ('fltt', '2'),
            ('invt', '2'),
            ('fid', 'f3'),
            ('fs', 'm:0+t:5'),  # 沪深300参数
            ('fields', 'f1,f2,f3,f9,f12,f14,f20'),
            ('tradeDate', current_date.strftime("%Y%m%d"))  # 关键日期参数
        )
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = json.loads(response.text)
            
            if data['data']['diff']:
                pe = data['data']['diff'][0]['f9']  # PE字段
                pe_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'pe': float(pe) if pe else None
                })
            time.sleep(0.5)  # 防止请求过快
        except Exception as e:
            print(f"{current_date} PE获取失败: {str(e)}")
        
        current_date += timedelta(days=1)
    
    return pd.DataFrame(pe_data)

# ================== 技术指标计算 ==================
def calculate_ma250(df):
    """计算250日均线"""
    if len(df) >= 250:
        df['ma250'] = df['close_price'].astype(float).rolling(250).mean()
    else:
        print("数据不足250天，无法计算MA250")
        df['ma250'] = None
    return df

# ================== 主程序 ==================
def main(stock_code, years=3):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*years)
    
    # 获取目标股票数据
    main_df = get_sohu_stock_data(stock_code, start_date, end_date)
    if main_df.empty:
        return
    
    # 获取沪深300PE数据（网页4方法）
    pe_df = get_hs300_pe_history(start_date, end_date)
    
    # 获取国债ETF数据
    bond_df = get_sohu_stock_data("000012", start_date, end_date)
    bond_df.rename(columns={'close_price':'bond_price'}, inplace=True)
    
    # 获取黄金ETF数据 
    gold_df = get_sohu_stock_data("518880", start_date, end_date)
    gold_df.rename(columns={'close_price':'gold_price'}, inplace=True)
    
    # 数据合并
    merged_df = pd.merge(main_df, pe_df, on='date', how='left')
    merged_df = calculate_ma250(merged_df)
    merged_df = pd.merge(merged_df, bond_df, on='date', how='left')
    merged_df = pd.merge(merged_df, gold_df, on='date', how='left')
    
    # 补充字段（需其他数据源）
    merged_df['vix_index'] = None  # 波动率指数需专业接口
    
    # 格式化输出
    final_df = merged_df[[
        'date', 'pe', 'close_price', 'ma250',
        'bond_price', 'vix_index', 'gold_price'
    ]]
    final_df['date'] = final_df['date'].dt.strftime('%Y-%m-%d')
    
    # 保存Excel
    final_df.to_excel(f"{stock_code}_history_data.xlsx", index=False)
    print(f"文件已保存为 {stock_code}_history_data.xlsx")

if __name__ == "__main__":
    main("600519")  # 示例：贵州茅台
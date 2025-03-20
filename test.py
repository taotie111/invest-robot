import pandas as pd
import numpy as np
from scipy import stats

class InvestmentSimulator:
    def __init__(self, initial_capital=100000, base_invest=3000):
        # 初始化账户状态
        self.cash = initial_capital
        self.stock_shares = 0.0
        self.bond_shares = 0.0
        self.reserve = 6 * base_invest  # 应急储备金
        self.base_invest = base_invest
        self.operations_log = []
        
        # 策略参数
        self.PE_BANDS = [30, 60]  # 低估/高估分界线
        self.EMERGENCY_THRESHOLD = 15  # 应急加仓阈值
        self.consecutive_low = 0  # 连续低估计数
        
        # 市场数据存储
        self.hist_pe = pd.DataFrame(columns=['date', 'pe', 'close', 'ma250'])
        
    def update_market_data(self, new_data):
        """更新市场数据"""
        self.hist_pe = pd.concat([self.hist_pe, new_data], ignore_index=True)
        
    def calculate_pe_percentile(self, current_pe):
        """计算PE历史分位值（剔除极端值）"""
        # 获取过去10年数据（120个月）
        lookback = 120
        if len(self.hist_pe) < lookback:
            usable_data = self.hist_pe['pe']
        else:
            usable_data = self.hist_pe['pe'].iloc[-lookback:]
        
        # 剔除极端值
        filtered = usable_data[(usable_data >= 8) & (usable_data <= 20)]
        if len(filtered) < 2:
            return 50  # 默认中位数
            
        # 计算分位
        return stats.percentileofscore(filtered, current_pe)
        
    def execute_investment(self, current_date, pe, close_price):
        """执行每月定投操作"""
        # 计算PE分位
        pe_percentile = self.calculate_pe_percentile(pe)
        
        # 定投逻辑
        invest_amount = 0
        if pe_percentile < self.PE_BANDS[0]:
            invest_amount = self.base_invest * 2
            self.consecutive_low += 1
        elif self.PE_BANDS[0] <= pe_percentile <= self.PE_BANDS[1]:
            invest_amount = self.base_invest
            self.consecutive_low = 0
        else:
            self.consecutive_low = 0
            
        # 应急加仓检查
        if self.consecutive_low >= 3:
            emergency_amount = self.reserve * 0.5
            invest_amount += emergency_amount
            self.reserve -= emergency_amount
            self.consecutive_low = 0  # 重置计数器
            
        # 执行买入
        if invest_amount > 0 and self.cash >= invest_amount:
            self.stock_shares += invest_amount / close_price
            self.cash -= invest_amount
            self.operations_log.append({
                'date': current_date,
                'action': f'买入 {invest_amount:.0f} 元',
                'PE分位': pe_percentile
            })
            
        return pe_percentile
        
    def rebalance_portfolio(self, pe_percentile, stock_price, bond_price):
        """执行股债再平衡"""
        # 计算目标比例
        stock_ratio = 1 - max(0.3, pe_percentile/100)
        total_assets = self.cash + self.stock_shares*stock_price + self.bond_shares*bond_price
        
        # 计算目标市值
        target_stock = total_assets * stock_ratio
        target_bond = total_assets * (1 - stock_ratio)
        
        # 调整持仓
        delta_stock = (target_stock - self.stock_shares*stock_price) / stock_price
        delta_bond = (target_bond - self.bond_shares*bond_price) / bond_price
        
        # 执行交易（假设可以部分交易）
        self.stock_shares += delta_stock
        self.bond_shares += delta_bond
        self.cash -= (delta_stock*stock_price + delta_bond*bond_price)
        
        self.operations_log.append({
            'date': current_date,
            'action': f'调仓至股票 {stock_ratio*100:.1f}%',
            'PE分位': pe_percentile
        })
    
    def check_profit_conditions(self, current_price, ma250, macd_signal):
        """复合止盈检查"""
        # 均线偏离检查
        price_deviation = (current_price - ma250) / ma250
        if price_deviation > 0.2:
            sell_percent = min(1, (price_deviation - 0.2) // 0.05 * 0.2)
            if sell_percent > 0:
                shares_to_sell = self.stock_shares * sell_percent
                self.cash += shares_to_sell * current_price
                self.stock_shares -= shares_to_sell
                self.operations_log.append({
                    'date': current_date,
                    'action': f'均线偏离止盈 {sell_percent*100:.0f}%'
                })
                
        # 强制清仓检查
        if self.pe_percentile >= 90:
            self.cash += self.stock_shares * 0.5 * current_price
            self.stock_shares *= 0.5
            self.operations_log.append({'date': current_date, 'action': 'PE清仓50%'})
            
        if macd_signal == 'bearish':
            self.cash += self.stock_shares * 0.3 * current_price
            self.stock_shares *= 0.7
            self.operations_log.append({'date': current_date, 'action': 'MACD清仓30%'})

# 使用示例（需配合历史数据加载）：
if __name__ == "__main__":
    # 初始化模拟器
    simulator = InvestmentSimulator(initial_capital=100000)
    
    # 假设从CSV加载历史数据（示例结构）
    # date | pe | close_price | ma250 | bond_price | macd_signal
    historical_data = pd.read_csv('historical_data.csv')
    
    for idx, row in historical_data.iterrows():
        simulator.update_market_data(pd.DataFrame([row]))
        
        if row['date'].endswith('-20'):  # 每月20日执行
            pe_percent = simulator.execute_investment(
                row['date'], row['pe'], row['close_price']
            )
            
            simulator.rebalance_portfolio(
                pe_percent, row['close_price'], row['bond_price']
            )
            
            simulator.check_profit_conditions(
                row['close_price'], row['ma250'], row['macd_signal']
            )
    
    # 输出最终结果
    print("操作记录：")
    print(pd.DataFrame(simulator.operations_log))
    
    final_value = simulator.cash + \
        simulator.stock_shares * historical_data['close_price'].iloc[-1] + \
        simulator.bond_shares * historical_data['bond_price'].iloc[-1]
    print(f"\n最终资产总值：{final_value:.2f}元")
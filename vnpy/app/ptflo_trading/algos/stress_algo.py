from vnpy.trader.constant import Offset, Direction
from vnpy.trader.object import TradeData
from vnpy.trader.engine import BaseEngine
from vnpy.trader.constant import OrderType, Offset, Direction

from vnpy.app.ptflo_trading import PtfloTemplate

import pymongo
import time
import pandas as pd


class StressAlgo(PtfloTemplate):
    """"""

    display_name = "压力测试"

    default_setting = {
        "algo_name": "",
        "gateway_name": "",
    }

    # "direction": [Direction.LONG.value, Direction.SHORT.value],

    variables = [
        "ots",
        "otn",
        "oti",
        "tts",
        "ttn",
        "tti",
        "ttt",
        "total_volume",
        "traded"
    ]

    def __init__(
            self,
            algo_engine: BaseEngine,
            algo_name: str,
            setting: dict,
            gateway_name: str = None
    ):
        """"""
        if gateway_name is None:
            gateway_name = setting['gateway_name']
        super().__init__(algo_engine, algo_name, setting, gateway_name)

        # Parameters
        self.client = pymongo.MongoClient('192.168.2.181', 27017)
        self.db = self.client['Fundamental']
        self.cc = self.db['AIndexComponent']
        
        self.tested = False
        self.b500 = []
        self.b300 = []

        # Variables
        self.ots = 0
        self.otn = 0
        self.oti = 0
        self.tts = 0
        self.ttn = 0
        self.tti = 0
        self.ttt = 0
        self.total_volume = 0
        self.traded = 0

        self.put_parameters_event()
        self.put_variables_event()

    def parse_task(self):
        cursor = self.cc.find({"index_code" : "000905.SH","date": "2019-06-26"}, {'wind_code': 1, 'weight': 1})
        data500 = list(cursor)
        df500 = pd.DataFrame(data500)
        df500.loc[:, 'weight'] = df500['weight'] / df500['weight'].sum()
        df500['vt_symbol'] = df500['wind_code'].apply(lambda x: x.replace('SH', 'SSE') if x.endswith('SH') else x.replace('SZ', 'SZSE'))
        df500['volume'] = 3000000 * df500['weight']
        df500.loc[:, 'volume'] = 100*((df500['volume'] / 100).astype(int))
        df500 = df500[df500['volume'] >= 100]
        self.total_volume += df500['volume'].sum()
        self.b500 = df500.to_dict('records')
        
        cursor = self.cc.find({"index_code" : "000300.SH","date": "2019-06-26"}, {'wind_code': 1, 'weight': 1})
        data300 = list(cursor)
        df300 = pd.DataFrame(data300)
        df300.loc[:, 'weight'] = df300['weight'] / df300['weight'].sum()
        df300['vt_symbol'] = df300['wind_code'].apply(lambda x: x.replace('SH', 'SSE') if x.endswith('SH') else x.replace('SZ', 'SZSE'))
        df300['volume'] = 2000000 * df500['weight']
        df300.loc[:, 'volume'] = 100*((df300['volume'] / 100).astype(int))
        df300 = df300[df300['volume'] >= 100]
        self.total_volume += df300['volume'].sum()
        self.b300 = df300.to_dict('records')
        
        c500 = len(self.b500)
        c300 = len(self.b300)
        self.total_volume *= 2

        msg = u'交易任务解析完成，共有股票 %s 只，其中500成分 %s只， 300成分%s只, ' \
              u'总交易量 %s ' % (c500 + c300, c500, c300, self.total_volume)
        self.write_log(msg)
        self.put_variables_event()
    
    
    def on_start(self):
        """"""
        self.parse_task()
        
        self.write_log("开始执行测试任务")
        
        self.write_log("开始下单")
        self.ots = time.time()
        for i in range(2):
            for item in self.b500:
                self.buy(item['vt_symbol'], 0, item['volume'], order_type=OrderType.MARKET, offset=Offset.OPEN)
            for item in self.b300:
                self.buy(item['vt_symbol'], 0, item['volume'], order_type=OrderType.MARKET, offset=Offset.OPEN)
        self.otn = time.time()
        self.oti = int(self.otn - self.ots)
        self.write_log("下单完成，共耗时 %s 秒" % self.oti)
        self.put_variables_event()
        

    def on_trade(self, trade: TradeData):
        """"""
        if self.tts == 0:
            self.tts = time.time()
        self.ttn = time.time()
        self.traded += trade.volume


        if self.traded >= self.total_volume:
            self.tti = int(self.ttn - self.tts)
            self.ttt = int(self.ttn - self.ots)
            self.write_log(f"已交易数量：{self.traded}，总数量：{self.total_volume}")
            self.write_log(f"总成交回报持续{self.tti}秒")
            self.write_log(f"整个过程耗时{self.ttt}秒")
            self.stop()
        else:
            self.put_variables_event()

    def on_timer(self):
        """"""
        if self.ttn > 0:
             pt = time.time() - self.ttn
             if pt > 300:
                  self.tti = int(self.ttn - self.tts)
                  self.ttt = int(self.ttn - self.ots)
                  self.write_log(f"已交易数量：{self.traded}，总数量：{self.total_volume}")
                  self.write_log(f"总成交回报持续{self.tti}秒")
                  self.write_log(f"整个过程耗时{self.ttt}秒")

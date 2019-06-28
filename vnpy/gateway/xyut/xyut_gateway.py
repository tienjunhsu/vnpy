# encoding: UTF-8
"""
provide universe quote
"""
import redis
import threading
import time
from datetime import datetime
import pymongo

from vnpy.trader.constant import Exchange, Product

from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    OrderData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
    ContractData)

EXCHANGE_POSTFIX = {
    Exchange.SSE: 'SH',
    Exchange.SZSE: 'SZ',
}

SYMBOL_EXCHANGE_MAP = {
    'SH': Exchange.SSE,
    'SZ': Exchange.SZSE
}

EXCHANGE_QUOTE2VT = {
    'SSE': Exchange.SSE,
    'SZSE': Exchange.SZSE
}


class XyutGateway(BaseGateway):
    """provide universe quote"""

    default_setting = {
        'host': '192.168.2.112',
        'port': 6379,
        'db': 1
    }

    exchanges = list(EXCHANGE_QUOTE2VT.values())

    def __init__(self, event_engine, gateway_name='xyut'):
        """Constructor"""
        super(XyutGateway, self).__init__(event_engine, gateway_name)
        self.live = False
        self.is_connected = False
        self.quote_plate = dict()
        self.symbols = []

        self.r = None
        self.md_thread = None

    def connect(self, setting: dict = None):
        """"""
        if self.is_connected:
            self.write_log(u'当前已处于连接状态，不用重复连接')
            return
        if setting is None:
            setting = self.default_setting
        host = setting['host']
        port = setting['port']
        db = setting['db']

        self.write_log(u'Quote gateway 已连接')
        self.query_contracts()

        self.r = redis.StrictRedis(host=host, port=port, db=db)
        self.live = True
        self.md_thread = threading.Thread(target=self.loop_md_thread, args=())
        self.md_thread.start()

        self.is_connected = True

        self.write_log(u'Quote gateway 已就绪')

    def subscribe(self, req: SubscribeRequest):
        """"""
        if req.exchange in EXCHANGE_POSTFIX:
            wind_symbol = req.symbol + '.' + EXCHANGE_POSTFIX[req.exchange]
            if wind_symbol not in self.symbols:
                self.symbols.append(wind_symbol)
        else:
            self.write_log(u'当前行情不支持订阅的该合约 %s ' % req.vt_symbol)

    def loop_md_thread(self):
        while self.live:
            self.fetch_ticks()
            time.sleep(2)

    def fetch_ticks(self):
        if not self.in_trading():
            return
        if len(self.symbols) < 1:
            return
        datas = self.r.mget(self.symbols)
        for index, item in enumerate(datas):
            if item is not None:
                try:
                    wind_code = self.symbols[index]
                    item = eval(item)
                    item['wind_code'] = wind_code
                    self.onRtnDepthMarketData(item)
                except Exception as ee:
                    raise ee

    def in_trading(self):
        now = datetime.now().strftime('%H:%M')
        if now < '09:15':
            return False
        elif (now > '11:32') and (now < '12:58'):
            return False
        elif now > '15:02':
            return False
        else:
            return True

    def onRtnDepthMarketData(self, data: dict):
        """
        Callback of tick data update.
        """
        wind_code = data['wind_code']
        symbol = wind_code[:6]
        exchange = SYMBOL_EXCHANGE_MAP[wind_code[-2:]]

        str_datetime = data['date'] + ' ' + data['time']

        # Note: from easyquotation, turnover is volume, volume is amount
        tick = TickData(
            symbol=symbol,
            exchange=exchange,
            datetime=datetime.strptime(str_datetime, "%Y-%m-%d %H:%M:%S"),
            name=data['name'],
            volume=data["turnover"],
            amount=data["volume"],
            last_price=data["now"],
            open_price=data["open"],
            high_price=data["high"],
            low_price=data["low"],
            pre_close=data["close"],
            gateway_name=self.gateway_name
        )
        for i in range(1, 6):
            tick.__dict__['bid_price_' + str(i)] = data['bid' + str(i)]
            tick.__dict__['bid_volume_' + str(i)] = data['bid' + str(i) + '_volume']
            tick.__dict__['ask_price_' + str(i)] = data['ask' + str(i)]
            tick.__dict__['ask_volume_' + str(i)] = data['ask' + str(i) + '_volume']
        if wind_code in self.quote_plate:
            if tick.datetime > self.quote_plate[wind_code].datetime:
                self.push_tick(tick, wind_code)
        else:
            self.push_tick(tick, wind_code)

    def push_tick(self, tick: TickData, wind_code: str):
        self.on_tick(tick)
        self.quote_plate[wind_code] = tick

    def send_order(self, req: OrderRequest):
        """"""
        pass

    def cancel_order(self, req: CancelRequest):
        """"""
        pass

    def query_account(self):
        """"""
        pass

    def query_position(self):
        """"""
        pass

    def query_contracts(self, setting=None):
        """query contract"""
        if setting is None:
            setting = {'host': '192.168.2.181', 'port': 27017, 'db': 'Fundamental', 'collection': 'SectorContract'}
        client = pymongo.MongoClient(setting['host'], setting['port'])
        cc = client[setting['db']][setting['collection']]
        cursor = cc.find({'exchange': {'$in': ['SSE', 'SZSE']}}, {'_id': 0, 'code': 1, 'name': 1, 'exchange': 1})
        for item in cursor:
            self.onRspQryInstrument(item)
        self.write_log(u'合约信息查询成功')

    def onRspQryInstrument(self, data):
        """push contract data"""
        contract = ContractData(
            symbol=data['code'],
            exchange=EXCHANGE_QUOTE2VT[data['exchange']],
            name=data['name'],
            product=Product.EQUITY,
            size=1,
            pricetick=0.01,
            gateway_name=self.gateway_name
        )
        self.on_contract(contract)

    def close(self):
        """"""
        self.live = False
        self.symbols = []
        self.r = None
        self.quote_plate = dict()
        self.md_thread = None

    def on_order(self, order: OrderData):
        """"""
        pass

    def get_order(self, orderid: str):
        """"""
        return None

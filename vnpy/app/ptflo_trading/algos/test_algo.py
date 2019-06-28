from vnpy.trader.constant import Offset, Direction
from vnpy.trader.object import TradeData
from vnpy.trader.engine import BaseEngine

from vnpy.app.ptflo_trading import PtfloTemplate


class TestAlgo(PtfloTemplate):
    """"""

    display_name = "篮子交易测试"

    default_setting = {
        "algo_name": "",
        "str_vt_symbol_list": "",
        "gateway_name": "",
        "str_price_list": "",
        "str_volume_list": "",
        "time": 600,
        "interval": 60
    }

    # "direction": [Direction.LONG.value, Direction.SHORT.value],

    variables = [
        "traded",
        "total_volume",
        "timer_count",
        "total_count"
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
        self.str_vt_symbol_list = setting['str_vt_symbol_list']
        self.str_price_list = setting['str_price_list']
        self.str_volume_list = setting['str_volume_list']

        self.vt_symbol_list = []
        self.tasks = dict()

        self.time = setting["time"]
        self.interval = setting["interval"]

        # Variables
        self.total_volume = 0
        self.timer_count = 0
        self.total_count = 0
        self.traded = 0

        self.parse_task()

        self.subscribe(self.vt_symbol_list)
        self.put_parameters_event()
        self.put_variables_event()

    def parse_task(self):
        vt_symbol_list = self.str_vt_symbol_list.split(',')
        price_list = self.str_price_list.split(',')
        volume_list = self.str_volume_list.split(',')

        assert len(vt_symbol_list) == len(price_list) == len(volume_list)

        for index, vt_symbol in enumerate(vt_symbol_list):
            item = {'vt_symbol': vt_symbol,
                    'volume': abs(int(volume_list[index])),
                    'price': float(price_list[index]),
                    'traded': 0}
            item['left_volume'] = item['volume']
            if int(volume_list[index]) >= 0:
                item['direction'] = Direction.LONG
                item['offset'] = Offset.OPEN
            else:
                item['direction'] = Direction.SHORT
                item['offset'] = Offset.CLOSE
            self.tasks[vt_symbol] = item
            self.vt_symbol_list.append(vt_symbol)

        self.vt_symbol_list = list(set(vt_symbol_list))

        long_count = 0
        short_count = 0
        total_count = 0

        for k, v in self.tasks.items():
            self.total_volume += v['volume']
            total_count += 1
            if v['direction'] == Direction.LONG:
                long_count += 1
            else:
                short_count += 1

        msg = u'交易任务解析完成，共有股票 %s 只，其中买入 %s只， 卖出%s只, ' \
              u'总交易量 %s' % (total_count, long_count, short_count, self.total_volume)
        self.write_log(msg)

    def on_trade(self, trade: TradeData):
        """"""
        self.traded += trade.volume

        vt_symbol = trade.vt_symbol
        item = self.tasks[vt_symbol]
        item['traded'] += trade.volume
        item['left_volume'] -= trade.volume

        if self.traded >= self.total_volume:
            self.write_log(f"已交易数量：{self.traded}，总数量：{self.total_volume}")
            self.stop()
        else:
            self.put_variables_event()

    def on_timer(self):
        """"""
        self.timer_count += 1
        self.total_count += 1
        self.put_variables_event()

        if self.total_count >= self.time:
            self.write_log("执行时间已结束，停止任务")
            self.stop()
            return

        if self.timer_count < self.interval:
            return
        self.timer_count = 0

        self.cancel_all()

        for vt_symbol, item in self.tasks.items():
            # vt_symbol = item['vt_symbol']
            tick = self.get_tick(vt_symbol)
            if not tick:
                continue

            item = self.tasks[vt_symbol]
            if item['left_volume'] < 100:
                continue

            left_volume = item['left_volume']
            order_volume = 100 * int((left_volume / ((self.time - self.total_count) / self.interval)) / 100)
            if order_volume < 100:
                order_volume = 100

            if item['direction'] == Direction.LONG:
                if tick.ask_price_1 <= item['price']:
                    self.buy(vt_symbol, item['price'],
                             order_volume, offset=Offset.OPEN)
            else:
                if tick.bid_price_1 >= item['price']:
                    self.sell(vt_symbol, item['price'],
                              order_volume, offset=Offset.CLOSE)

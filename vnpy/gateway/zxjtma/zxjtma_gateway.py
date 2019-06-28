# encoding: UTF-8
"""
provide universe quote
"""
import time
import logging
from datetime import datetime
from pathlib import Path
from itertools import islice

from vnpy.event import EVENT_TIMER
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from vnpy.trader.constant import Exchange, Product, Direction, OrderType, Offset, Status

from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    OrderData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
    ContractData, HistoryRequest, AccountData, PositionData, TradeData)

EXCHANGE_POSTFIX = {
    Exchange.SSE: 'SH',
    Exchange.SZSE: 'SZ',
}

EXCHANGE_2MA = {
    Exchange.SSE: '10',
    Exchange.SZSE: '00',
    # Exchange.SHFE: 'A0',
    # Exchange.DCE: 'B0',
    # Exchange.CZCE: 'C0',
    # Exchange.CFFEX: 'G0'
}

MA2_EXCHANGE = {
    '10': Exchange.SSE,
    '00': Exchange.SZSE
}

EXCHANGE_MATYPE = {
    Exchange.SSE: '0',
    Exchange.SZSE: '0',
    # Exchange.SHFE: '2',
    # Exchange.DCE: '2',
    # Exchange.CZCE: '2',
    # Exchange.CFFEX: '2'
}

DIRECTION_2MA = {
    Direction.LONG: '100',
    Direction.SHORT: '101'
}

MA2_DIRECTION = {
    '100': Direction.LONG,
    '101': Direction.SHORT
}

ORDERTYPE_2MA = {
    OrderType.LIMIT: '100',
    OrderType.MARKET: '121',#153
    OrderType.STOP: '100',
    OrderType.FAK: '152',
    OrderType.FOK: '151'
}

MA2_ORDERTYPE = {
    '100': OrderType.LIMIT,
    '121': OrderType.MARKET,# 153
    '152': OrderType.FAK,
    '151': OrderType.FOK
}

MA2_STATUS = {
    u'已报': Status.NOTTRADED,
    u'已成': Status.ALLTRADED,
    u'废单': Status.REJECTED,
    u'已撤': Status.CANCELLED,
    u'部分成交': Status.PARTTRADED,
    u'部撤': Status.PARTTRADED,

}

SYMBOL_EXCHANGE_MAP = {
    'SH': Exchange.SSE,
    'SZ': Exchange.SZSE
}

EXCHANGE_QUOTE2VT = {
    'SSE': Exchange.SSE,
    'SZSE': Exchange.SZSE
}


def gateway_inited(func):
    def wrapper(*args, **kwargs):
        cls_instance = args[0]
        if not cls_instance.inited:
            msg = u'gateway 还未完成账户信息查询，当前不支持该操作'
            cls_instance.write_log(msg)
            return
        result = func(*args, **kwargs)
        return result

    return wrapper


class ZxjtmaGateway(BaseGateway):
    """provide universe quote"""

    default_setting = {
        'path': '~/Zxjtma/',
    }

    exchanges = list(EXCHANGE_QUOTE2VT.values())

    def __init__(self, event_engine, gateway_name='zxjtma'):
        """Constructor"""
        super(ZxjtmaGateway, self).__init__(event_engine, gateway_name)
        self.is_connected = False
        self.today = datetime.now().strftime('%Y%m%d')

        self.count = 0
        self.query_functions = []

        self.order_file = None
        self.on_order_file = None
        self.reject_order_file = None
        self.position_file = None
        self.account_file = None
        self.trade_file = None

        self.folder_path = None
        self.order_ref = 0
        self.activate_orders = dict()

        self.observer = None
        self.watch_handler = None

        self.account_inited = False
        self.position_inited = False
        self.inited = False

        self.order_line_count = 0
        self.trade_line_count = 0
        self.reject_order_line_count = 0

    def connect(self, setting: dict = None):
        """"""
        if self.is_connected:
            self.write_log(u'当前已处于连接状态，不用重复连接')
            return
        if setting is None:
            setting = self.default_setting
        folder_path = setting['path']
        self.folder_path = Path(folder_path)
        if not self.folder_path.exists():
            self.folder_path.mkdir()
        else:
            if not self.folder_path.is_dir():
                self.write_log(u'该路径是一个文件，无法创建连接')
                return
        self.order_file = self.folder_path.joinpath(self.gateway_name + 'orders.txt')
        self.on_order_file = self.folder_path.joinpath(self.today + u'委托确认.txt')
        self.reject_order_file = self.folder_path.joinpath(self.today + u'拒单委托.txt')
        self.position_file = self.folder_path.joinpath(self.today + u'持仓.txt')
        self.account_file = self.folder_path.joinpath(self.today + u'资金.txt')
        self.trade_file = self.folder_path.joinpath(self.today + u'成交.txt')
        self.init_order_file()

        self.watch_handler = WatchHandler(self)
        self.observer = Observer()

        self.is_connected = True

        self.init_query()

        self.write_log(u'gateway 已就绪, 等待初始化')

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

    def init_query(self):
        """"""
        self.count = 0
        self.query_functions = [self.query_account, self.query_position]
        self.event_engine.register(EVENT_TIMER, self.process_timer_event)

    def process_timer_event(self, event):
        """"""
        self.count += 1
        if self.count < 2:
            return
        self.count = 0

        func = self.query_functions.pop(0)
        func()
        self.query_functions.append(func)

    def check_init(self):
        if self.inited:
            return
        if self.position_inited and self.account_inited:
            self.init_line_count()
            self.set_file_watcher()
            self.inited = True
            self.write_log(u'账户初始化完成')

    def set_file_watcher(self):
        # print(self.folder_path.as_posix())
        self.observer.schedule(self.watch_handler, self.folder_path.as_posix())

        self.observer.start()

    def init_line_count(self):
        with self.on_order_file.open('r') as f:
            for line in f.readlines():
                self.order_line_count += 1
        with self.reject_order_file.open('r') as f:
            for line in f.readlines():
                self.reject_order_line_count += 1
        with self.trade_file.open('r') as f:
            for line in f.readlines():
                self.trade_line_count += 1

    def init_order_file(self):
        columns = [u'//类型 ', u'交易板块', u'证券代码', u'买卖行为', u'业务活动', u'委托价格',
                   u'委托数量', u'委托标识']
        content = self.gen_content(columns)
        with self.order_file.open('w') as f:
            f.write(content)

    def gen_content(self, content_list):
        content = '    '.join(content_list)
        content += '\n'
        return content

    def close(self):
        """
        Close gateway connection.
        """
        if self.observer is not None:
            self.observer.stop()
        self.observer = None
        self.watch_handler = None

        self.order_file = None
        self.on_order_file = None
        self.reject_order_file = None
        self.position_file = None
        self.account_file = None
        self.trade_file = None

    def subscribe(self, req: SubscribeRequest):
        """
        Subscribe tick data update.
        """
        pass

    @gateway_inited
    def send_order(self, req: OrderRequest) -> str:
        """
        Send a new order to server.

        implementation should finish the tasks blow:
        * create an OrderData from req using OrderRequest.create_order_data
        * assign a unique(gateway instance scope) id to OrderData.orderid
        * send request to server
            * if request is sent, OrderData.status should be set to Status.SUBMITTING
            * if request is failed to sent, OrderData.status should be set to Status.REJECTED
        * response on_order:
        * return OrderData.vt_orderid

        :return str vt_orderid for created OrderData
        """
        # print('send order..................')
        return self.write_order(req)

    def write_order(self, req: OrderRequest) -> str:
        # print('write order.......')
        # print(req.__dict__)
        order_columns = ['0', EXCHANGE_2MA[req.exchange], req.symbol, DIRECTION_2MA[req.direction],
                         ORDERTYPE_2MA[req.type], str(round(req.price, 2)), str(req.volume)]
        self.order_ref += 1
        str_time = time.strftime('%H%M%S')
        orderid = f"{str_time}_{self.order_ref}"
        order_columns.append(orderid)
        order_content = self.gen_content(order_columns)
        # print(order_content)
        with self.order_file.open('a') as f:
            f.write(order_content)
        order = req.create_order_data(orderid, self.gateway_name)
        order.time = datetime.now().strftime('%H:%M:%S.%f')[:12]
        # print(order.__dict__)
        self.activate_orders[orderid] = order
        self.on_order(order)
        return order.vt_orderid

    @gateway_inited
    def cancel_order(self, req: CancelRequest):
        """
        Cancel an existing order.
        implementation should finish the tasks blow:
        * send request to server
        """
        if req.orderid not in self.activate_orders:
            msg = u'撤销的订单%s不存在' % req.orderid
            self.write_log(msg)
            return
        order = self.activate_orders[req.orderid]
        order_columns = ['0', EXCHANGE_2MA[order.exchange], order.symbol, DIRECTION_2MA[order.direction],
                         ORDERTYPE_2MA[order.type], str(order.price), str(order.volume), '-' + order.orderid]
        order_content = self.gen_content(order_columns)
        with self.order_file.open('a') as f:
            f.write(order_content)

    def query_account(self):
        """
        Query account balance.
        """
        if not self.account_file.exists():
            return
        info = None
        with self.account_file.open('r') as f:
            for line in islice(f, 1, None):
                info = line
                break
        if info is None:
            # msg = u'当前没有查询到资金信息'
            # self.write_log(msg)
            return
        info = info.split()
        account = AccountData(gateway_name=self.gateway_name, accountid=info[1], balance=float(info[2]),
                              frozen=float(info[4]))
        self.on_account(account)
        if not self.account_inited:
            self.account_inited = True
            self.check_init()

    def query_position(self):
        """
        Query holding positions.
        """
        if not self.position_file.exists():
            return
        positions = []
        with self.position_file.open('r') as f:
            for line in islice(f, 1, None):
                if not line:
                    break
                item = line.split()
                if len(item) > 0:
                    v = int(item[5])
                    yv = int(item[4])
                    fv = v - yv
                    position = PositionData(gateway_name=self.gateway_name, symbol=item[2],
                                            exchange=MA2_EXCHANGE[item[9]], direction=Direction.LONG,
                                            volume=v, frozen=fv, price=float(item[6]),
                                            pnl=float(item[7]), yd_volume=yv)
                    positions.append(position)
        if len(positions) > 0:
            for position in positions:
                self.on_position(position)
            if not self.position_inited:
                self.position_inited = True
                self.check_init()

    def query_history(self, req: HistoryRequest):
        """
        Query bar history data.
        """
        pass

    def get_default_setting(self):
        """
        Return default setting dict.
        """
        return self.default_setting

    def dispatch_on_order(self):
        # print('dispatch_on_order.....')
        with self.on_order_file.open('r') as f:
            for line in islice(f, self.order_line_count, None):
                self.order_line_count += 1
                if not line:
                    break
                item = line.split()
                if len(item) < 11:
                     # 撤单可能没有后两项
                     item += ['0'] * (11 - len(item))
                # print(item)
                orderid = item[2]
                if orderid.startswith('-'):
                     orderid = orderid[1:]
                symbol = item[3]
                action_code = item[4]
                action_name = item[5]
                volume = int(float(item[6]))
                price = float(item[7])
                traded = int(float(item[9]))
                status = item[8]
                status = MA2_STATUS[status]
                str_time = item[0]
                # 由于拒单是在其他文件的，为了维持推送顺序，只推送未完成的订单
                if orderid in self.activate_orders:
                    order = self.activate_orders[orderid]
                    order.volume = volume
                    order.price = price
                    order.traded = traded
                    order.status = status
                    # print(order.__dict__)
                    self.on_order(order)
                else:
                    # order = OrderData(symbol=symbol, exchange=self.get_exchange_by_symbol(symbol), orderid=orderid,
                    #                   direction=MA2_DIRECTION[action_code], offset=self.get_offset(action_code),
                    #                   price=price, volume=volume, traded=traded, status=status, time=str_time,
                    #                   gateway_name=self.gateway_name)
                    # print(order.__dict__)
                    # self.on_order(order)
                    continue

    def dispatch_on_trade(self):
        # print('dispatch_on_trade.....')
        with self.trade_file.open('r') as f:
            for line in islice(f, self.trade_line_count, None):
                self.trade_line_count += 1
                if not line:
                    break
                item = line.split()
                # print(len(item))
                if len(item) < 19:
                     item += ['0'] * (19 - len(item))
                # print(item)
                orderid = item[2]
                if orderid.startswith('-'):
                    orderid = orderid[1:]
                tradeid = item[3]
                symbol = item[5]
                action_code = item[6]
                action_name = item[7]
                volume = int(float(item[8]))
                price = float(item[9])
                status = item[14]
                is_part_cancel = status == u'部撤'
                status = MA2_STATUS[status]
                str_time = item[0]
                # 要特别注意一下部撤这个状态，剩下得是还处于挂单还是成交了
                if status == Status.CANCELLED or status == Status.REJECTED:
                    if orderid in self.activate_orders:
                        order = self.activate_orders.pop(orderid)
                        order.status = Status.CANCELLED
                        self.on_order(order)
                elif status == Status.ALLTRADED or status == Status.PARTTRADED:
                    trade = TradeData(gateway_name=self.gateway_name, symbol=symbol, orderid=orderid, tradeid=tradeid,
                                      direction=MA2_DIRECTION[action_code], offset=self.get_offset(action_code),
                                      exchange=self.get_exchange_by_symbol(symbol), price=price, volume=volume,
                                      time=str_time)
                    # print(trade.__dict__)
                    self.on_trade(trade)
                    if orderid in self.activate_orders:
                        if is_part_cancel:
                            # 处理订单部撤状态
                            order = self.activate_orders.pop(orderid)
                            status = Status.CANCELLED
                        elif status == Status.ALLTRADED:
                            order = self.activate_orders.pop(orderid)
                        else:
                            order = self.activate_orders[orderid]
                        order.status = status
                        order.traded += volume
                        self.on_order(order)
                else:
                    msg = 'Unknown trade type:'
                    msg += ','.join(item)
                    self.write_log(msg)

    def dispatch_reject_order(self):
        #print('dispatch_reject_order....')
        with self.reject_order_file.open('r') as f:
            for line in islice(f, self.reject_order_line_count, None):
                self.reject_order_line_count += 1
                if not line:
                    break
                item = line.split()
                # print(len(item))
                if len(item) < 16:
                     item += ['0'] * (16 - len(item))
                # print(item)
                orderid = item[3]
                if orderid.startswith('-'):
                     orderid = orderid[1:]
                symbol = item[4]
                action_code = item[5]
                action_name = item[6]
                volume = int(float(item[7]))
                price = float(item[10])
                status = item[12]
                status = MA2_STATUS[status]
                str_time = item[0]
                if status == Status.REJECTED:
                    if orderid in self.activate_orders:
                        order = self.activate_orders.pop(orderid)
                        order.status = Status.REJECTED
                        self.on_order(order)
                    else:
                        # order = OrderData(symbol=symbol, exchange=self.get_exchange_by_symbol(symbol),
                        #                   orderid=orderid,
                        #                   direction=MA2_DIRECTION[action_code], offset=self.get_offset(action_code),
                        #                   price=price, volume=volume, traded=0, status=status, time=str_time,
                        #                   gateway_name=self.gateway_name)
                        # self.on_order(order)
                        continue

    def get_exchange_by_symbol(self, symbol):
        if symbol.startswith('60'):
            return Exchange.SSE
        else:
            return Exchange.SZSE

    def get_offset(self, action_code):
        if action_code == '100':
            return Offset.OPEN
        elif action_code == '101':
            return Offset.CLOSE
        else:
            return Offset.NONE


class WatchHandler(FileSystemEventHandler):

    def __init__(self, gateway):
        super(WatchHandler, self).__init__()
        self.gateway = gateway

    def on_created(self, event):
        # print('RejectOrderHandler on created')
        pass

    def on_modified(self, event):
        if event.is_directory:
            return
        src = event.src_path
        if src.endswith(u'成交.txt'):
            self.gateway.dispatch_on_trade()
        elif src.endswith(u'委托确认.txt'):
            self.gateway.dispatch_on_order()
        elif src.endswith(u'拒单委托.txt'):
            self.gateway.dispatch_reject_order()


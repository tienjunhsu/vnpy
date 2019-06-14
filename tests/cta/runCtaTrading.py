# encoding:utf-8
import multiprocessing
from time import sleep
from datetime import datetime, time

from vnpy.trader.object import LogData, SubscribeRequest

from vnpy.event import EventEngine, Event
from vnpy.trader.event import *    # EVENT_LOG
from vnpy.trader.engine import MainEngine, LogEngine
from vnpy.gateway.ctp import CtpGateway
from vnpy.gateway.quote import QuoteGateway
from vnpy.app.cta_strategy import CtaStrategyApp
from vnpy.app.cta_strategy.base import EVENT_CTA_LOG

from vnpy.trader.constant import Exchange


#----------------------------------------------------------------------
def processErrorEvent(event):
    """
    处理错误事件
    错误信息在每次登陆后，会将当日所有已产生的均推送一遍，所以不适合写入日志
    """
    error = event.data
    print('on_event')
    print(error)
    # print(u'错误代码：%s，错误信息：%s' %(error.errorID, error.errorMsg))


# ----------------------------------------------------------------------
def runChildProcess():
    """子进程运行函数"""
    print('-' * 20)

    ee = EventEngine()
    # le.info(u'事件引擎创建成功')
    print(u'事件引擎创建成功')

    me = MainEngine(ee)
    me.add_gateway(CtpGateway, 'td_ctp')
    me.add_gateway(QuoteGateway, 'quote')
    me.add_app(CtaStrategyApp)
    # le.info(u'主引擎创建成功')
    print(u'主引擎创建成功')

    gateways = me.get_all_gateway_names()
    print(gateways)

    # 创建日志引擎
    le = LogEngine(me, ee)
    # le.setLogLevel(le.LEVEL_INFO)
    le.add_console_handler()
    le.add_file_handler()

    # le.info(u'启动CTA策略运行子进程')
    print(u'启动CTA策略运行子进程')

    ee.register(EVENT_LOG, le.process_log_event)
    ee.register(EVENT_CTA_LOG, le.process_log_event)
    ee.register(EVENT_LOG, processErrorEvent)
    ee.register(EVENT_CTA_LOG, processErrorEvent)
    ee.register(EVENT_ACCOUNT, processErrorEvent)
    ee.register(EVENT_POSITION, processErrorEvent)
    ee.register(EVENT_TICK, processErrorEvent)
    # ee.register(EVENT_ERROR, processErrorEvent)
    # le.info(u'注册日志事件监听')
    print(u'注册日志事件监听')

    # me.dbConnect()

    ctp_setting = {
        "用户名": "xxxx",
        "密码": "xxxxx",
        "经纪商代码": "9999",
        "交易服务器": "tcp://180.168.146.187:10001",
        "行情服务器": "tcp://180.168.146.187:10011",
        "产品名称": "",
        "授权编码": ""
    }

    # me.connect(ctp_setting, 'td_ctp')
    # le.info(u'连接CTP接口')
    me.connect(None, 'quote')
    print(u'连接CTP接口')

    sleep(10)  # 等待CTP接口初始化
    # me.dataEngine.saveContracts()  # 保存合约信息到文件
    # td_ctp = me.get_gateway('td_ctp')
    # td_ctp.query_account()
    # td_ctp.query_position()

    cta = me.apps[CtaStrategyApp.app_name]
    print(cta)

    # cta.loadSetting()
    # le.info(u'CTA策略载入成功')
    #
    # cta.initAll()
    # le.info(u'CTA策略初始化成功')
    #
    # cta.startAll()
    # le.info(u'CTA策略启动成功')
    print('初始化完成')

    print(u'开始订阅行情')
    req = SubscribeRequest(
        symbol='000001', exchange=Exchange.SSE)
    me.subscribe(req, 'quote')
    req = SubscribeRequest(
        symbol='600000', exchange=Exchange.SZSE)
    me.subscribe(req, 'quote')
    print(u'行情订阅完成')

    while True:
        # log = LogData(msg=datetime.now().strftime('%H:%M:%S'), gateway_name='td_ctp')
        # print(log)
        # event = Event(EVENT_LOG, log)
        # ee.put(event)
        sleep(3)


if __name__ == '__main__':
    runChildProcess()
from pathlib import Path

from vnpy.trader.app import BaseApp

from .engine import PtfloEngine, APP_NAME
from .template import PtfloTemplate


class PtfloTradingApp(BaseApp):
    """"""

    app_name = APP_NAME
    app_module = __module__
    app_path = Path(__file__).parent
    display_name = "篮子交易"
    engine_class = PtfloEngine
    widget_name = "PtfloManager"
    icon_name = "ptflo.ico"

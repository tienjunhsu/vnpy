.def("reqUserLogin", &MdApi::reqUserLogin)
.def("reqUserLogout", &MdApi::reqUserLogout)

.def("onFrontConnected", &MdApi::onFrontConnected)
.def("onFrontDisconnected", &MdApi::onFrontDisconnected)
.def("onHeartBeatWarning", &MdApi::onHeartBeatWarning)
.def("onRspUserLogin", &MdApi::onRspUserLogin)
.def("onRspUserLogout", &MdApi::onRspUserLogout)
.def("onRspError", &MdApi::onRspError)
.def("onRspSubMarketData", &MdApi::onRspSubMarketData)
.def("onRspUnSubMarketData", &MdApi::onRspUnSubMarketData)
.def("onRspSubForQuoteRsp", &MdApi::onRspSubForQuoteRsp)
.def("onRspUnSubForQuoteRsp", &MdApi::onRspUnSubForQuoteRsp)
.def("onRtnDepthMarketData", &MdApi::onRtnDepthMarketData)
.def("onRtnForQuoteRsp", &MdApi::onRtnForQuoteRsp)
.def("onRtnDeferDeliveryQuot", &MdApi::onRtnDeferDeliveryQuot)
;

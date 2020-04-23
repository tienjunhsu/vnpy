# encoding:utf-8
from huobi.HuobiDMService import HuobiDM
from pprint import pprint

#### input huobi dm url
URL = 'https://api.hbdm.com'

####  input your access_key and secret_key below:
ACCESS_KEY = ''
SECRET_KEY = ''


dm = HuobiDM(URL, ACCESS_KEY, SECRET_KEY)

result = dm.api_get('api/v1/contract_contract_info', {})
print(result)
result = dm.api_post('api/v1/contract_account_info', {})
print(result)

# trigger order test
data = {'contract_code': 'EOS200626', 'trigger_type': 'ge', 'trigger_price': 2.650, 
       'order_price': 2.66, 'volume': 1, 'direction': 'buy', 'offset': 'open',
       'lever_rate': 20}
result = dm.api_post('api/v1/contract_trigger_order', data)
## result: {'status': 'ok', 'data': {'order_id': 10658341, 'order_id_str': '10658341'}, 'ts': 1587611237390}
print(result)
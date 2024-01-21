from urllib.request import urlopen, Request
import json
import datetime
import statistics
import numpy as np

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.3'}
DUMP_URL = "https://chisel.weirdgloop.org/gazproj/gazbot/os_dump.json"
URL_90D_BASE = 'https://api.weirdgloop.org/exchange/history/osrs/last90d?id='
URL_90D_TAIL = '&compress=true'

URL_ALL_BASE = "https://api.weirdgloop.org/exchange/history/osrs/all?id="
URL_ALL_TAIL = "&compress=true"

def get_item_data():
    '''
    Fetch a recent dump with data of all items in the game without price history.
    '''

    req = Request(url=DUMP_URL, headers=HEADERS)
    html = urlopen(req).read()

    data_all_raw = json.loads(html)
    last_update = datetime.datetime.fromtimestamp(data_all_raw['%JAGEX_TIMESTAMP%'])
    print(f'The fetched item data was last updated {last_update}, length ={len(data_all_raw)} ')

    data_all = {} # good dict

    for key, item in data_all_raw.items():
        if key.startswith('%'):
            continue
        data_all[int(key)] = item

    return data_all


def get_recent_vol_and_price(id):
    '''
    A function that calculates median volume and price over the last 90d for an item-id
    '''
    url = URL_90D_BASE + f'{id}' + URL_90D_TAIL
    req = Request(url=url, headers=HEADERS)
    html = urlopen(req).read()
    j = json.loads(html)
    #if id == 24609 or id == '24609':
    #print(id)
    print(j)
    #print(type(j))
    if 'error' in j.keys() and j['error'] == 'No results returned':
        return None, None
    j = j[f'{id}']
    if not j:
        return None, None

    volums = []
    prices = []
    for day in j:
        if len(day) < 3: # No volume
            volums.append(0)
            prices.append(day[1])
        else:
            volums.append(day[2])
            prices.append(day[1])
    
    return statistics.median(volums), statistics.median(prices)


# Pull price data for a given id
def get_data_for_id(id, url=None):
    if isinstance(id, int):
        id = f'{id}'

    if url == None:
        url = URL_ALL_BASE + id + URL_ALL_TAIL

    req = Request(url=url, headers=HEADERS)
    html = urlopen(req).read()
    j = json.loads(html)[f'{id}']

    prices = []
    timestamps = []
    vol = []
    for day in j:
        prices.append(day[1])
        timestamps.append( datetime.datetime.fromtimestamp( int(day[0]) / 1e3) )
        if len(day) < 3 or day[2] == None:
            vol.append(-1)
        else:
            vol.append(day[2])
    
    prices_n = np.empty(len(prices)).astype('int32')
    vol_n = np.empty(len(vol)).astype('int32')
    for i, p in enumerate(prices):
        prices_n[i] = p
        vol_n[i] = vol[i]
            
    return (prices_n, timestamps, vol_n)


# Pull price data for a given id, but only the most recent 90 days
def get_data_for_id_90d(id):
    if isinstance(id, int):
        id = f'{id}'

    url = URL_90D_BASE + id + URL_90D_TAIL
    return get_data_for_id(id, url=url)



#Find the latest timestamp within the /all data history
def get_latest_timestamp():
    p, t, v = get_data_for_id(453) #Coal
    return t[-1]
import datetime
import numpy as np

import os
from pathlib import Path
import pickle
import sys

#Remove dates that are over age_limit old from backtest_data.
def util_filter_dates(age_limit, item_price, item_dates, vol, backtest_date):

    start_date = datetime.datetime.now()
    if backtest_date != -1:
        start_date = backtest_date

    mask = np.ones(item_price.size)
    dates = []
    for i, d in enumerate(item_dates):
        age_days = (start_date - d).days
        if age_days > age_limit:
            mask[i] = 0
        else:
            dates.append(d)

    price = (mask*item_price)[np.nonzero(mask*item_price)]
    v = (mask*vol)[np.nonzero(mask*vol)]
    return (price, dates, v)

#Return a dict with price data sorted into different time periods
def util_get_period_pricing(prices, timestamps, vol, backtest_date=-1):
    r = {}
    r['1month'] = util_filter_dates(30, prices, timestamps, vol, backtest_date)
    r['3month'] = util_filter_dates(90, prices, timestamps, vol, backtest_date)
    r['6month'] = util_filter_dates(182, prices, timestamps, vol, backtest_date)
    r['12month'] = util_filter_dates(365, prices, timestamps, vol, backtest_date)
    r['24month'] = util_filter_dates(730, prices, timestamps, vol, backtest_date)
    r['all'] = (prices, timestamps, vol)
    return r


def util_cache_store(filename, data):
    if not os.path.exists('./cache/'):
        os.mkdir('./cache/')
    with open(f'cache/{filename}.dat', 'wb') as handle:
        pickle.dump(data, handle)



def util_cache_get(filename):
    if not os.path.exists('./cache/'):
        os.mkdir('./cache/')
    
    if not Path(f'./cache/{filename}.dat').is_file():
        if filename == 'current_iter':
            return 0
        else:
            raise Exception(f'Cache {filename} is accessed before it is created')
    else:
        with open(f'.cache/{filename}.dat', 'rb') as handle:
            return pickle.loads(handle.read())


#cut off latest dates to have a last date further back in time
def util_adjust_period_pricing(period_pricing, last_date):
    p, t, v = period_pricing['all']
    i = 0
    for i in range(len(t)):
        if t[i] > last_date:
            break

    if i == 0 or i == 1: return -1

    p = p[0:i-1]
    t = t[0:i-1]
    v = v[0:i-1]

    return util_get_period_pricing(p, t, v, backtest_date=t[-1])


#Progress bar like print start
def util_progress_start(title):
    sys.stdout.write(title)
    sys.stdout.flush()

#Progress bar like print update
def util_progress_update(msg):
    sys.stdout.write( msg + chr(8)*len(msg) )
    sys.stdout.flush()

#Progress bar like print end
def util_progress_end():
    sys.stdout.write("\n")
    sys.stdout.flush()
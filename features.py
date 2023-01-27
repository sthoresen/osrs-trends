import numpy as np
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates

from utils import util_cache_get, util_cache_store, util_get_period_pricing
import utils
from api import get_data_for_id

'''
Simple code do determine if the item is worthy of an investment.

Criteria:

* Current price needs be miniumum 20% lower than the highest 1year price. Feature: potential20
* Calculate the multiplier difference between the current and highest year price. This is the max_profit feature.
* Calculate an "avg line" that is horizontal, and the avg price of the last year.
* Calculate the number of times the graph has crossed this line (Note: A 5% move away from the line
is required before a new crossing counts). This number is the n_cross feature.
* Experiment with different maxProfit, n_cross requirements and ranking schemes.
* Another feature: The number of times the price has moved from current price to a new local high (min +5%),
and multiply this with the average percentage move in said moves. Feature: predecent_return. Also store 
the number of times seperately: n_precedent. NOTE: How to define local high?
* mean-dif: percentage dif between price and mean (lower = positive, higher = negative)

New thoughts: Maybe what I am really interested in is just the variance from the mean line. And I want to find
items with as high variance as possible. But still, I don't just want collapsing price or rising price, I still want
the chart to cross the mean line.

'''

class FeatureSet:
    def __init__(self, id, item, period_pricing, price, highest_1year, highest_period, potential20, max_profit, avg_line_num, margin, n_cross, avg_top, n_precedent, precedent_return, mean_dif):
        self.id = id
        self.item = item
        self.period_pricing = period_pricing
        self.price = price
        self.highest_1year = highest_1year
        self.highest_period = highest_period
        self.potential20 = potential20
        self.max_profit = max_profit
        self.avg_line_num = avg_line_num
        self.margin = margin
        self.n_cross = n_cross
        self.avg_top = avg_top
        self.n_precedent = n_precedent
        self.precedent_return = precedent_return
        self.mean_dif = mean_dif
        self.sorting_mode = None

    def set_sorting_mode(self, mode):
        self.sorting_mode = mode

    def __lt__(self, other):
        if self.sorting_mode == "precedent_return":
            return sum(self.precedent_return) < sum(other.precedent_return)
        elif self.sorting_mode == "max_profit":
            return sum(self.max_profit) < sum(other.max_profit)
        elif self.sorting_mode == "mean_dif":
            return sum(self.mean_dif) < sum(other.mean_dif)
        elif self.sorting_mode == "n_cross":
            return sum(self.n_cross) < sum(other.n_cross)
        elif self.sorting_mode == "n_precedent":
            return sum(self.n_precedent) < sum(other.n_precedent)
        else:
            raise Exception("Error: Sorting mode not recognized. Was set to: {self.sorting_mode}")

def get_current_price(item_price):
    #Expects np array
    return item_price[item_price.size-1]

def get_highest_1year_price(item_price, item_dates, backtest_date=None):
    #Expects np array
    mask = np.ones(item_price.size)
    for i, d in enumerate(item_dates):
        if not backtest_date:
            age_days = (datetime.datetime.now() - d).days
        else:
            age_days = (backtest_date - d).days
        if age_days > 365 or age_days < 0:
            mask[i] = 0

    return np.max(mask*item_price)

def get_highest_period(item_price): # Find highest price, none-applicable dates are already filtered out
    return np.max(item_price)

def get_lowest_1year_price(item_price, item_dates):
    #Expects np array
    mask = np.ones(item_price.size)
    for i, d in enumerate(item_dates):
        age_days = (datetime.datetime.now() - d).days
        if age_days > 365:
            mask[i] = 0

    return np.min((mask*item_price)[np.nonzero(mask*item_price)])

#Is current price 20% lower than 1 year highest price?
def get_potential20(item_price, item_dates, backtest_date=None):
    return get_highest_1year_price(item_price, item_dates, backtest_date=backtest_date)/get_current_price(item_price) >= 1.2

#Ratio highest 1 year price to current
def get_max_profit(item_price, item_dates):
    return get_highest_1year_price(item_price, item_dates)/get_current_price(item_price)

#Average price in period
def get_avg_line_num(item_price, item_dates):
    return (np.sum(item_price)/item_price.size).astype('int32')

def plot_avg_line(item_price, item_dates):
    plt.figure(figsize=(20, 20), dpi=80)
    plt_dates = matplotlib.dates.date2num(item_dates)
    plt.plot_date(plt_dates, item_price, '-', linewidth=2)

    mean1y = np.sum(item_price)/item_price.size
    mean_line = np.ones(item_price.size)*mean1y    

    plt.plot(plt_dates, mean_line, 'r-', linewidth=1)

#Calculate the crossing points between the price and the average price line
def get_crossing_points(item_price, item_dates):
    avg = get_avg_line_num(item_price, item_dates)

    over_line = item_price[0] > avg
    last_price = -1
    crossings = [] # index, price
    for i in range(item_price.size):
        price = item_price[i]

        if price > avg and not over_line:
            over_line = True
            if last_price != avg:
                crossings.append( (i, price, over_line) )
            else:
                crossings.append( (i-1, last_price, over_line) )
        elif price < avg and over_line:
            over_line = False
            if last_price != avg:
                crossings.append( (i, price, over_line) )
            else:
                crossings.append( (i-1, last_price, over_line) )

        last_price = price

    return crossings

#Calculates top and bottom points for the price data
def get_extreme_points(item_price, item_dates):
    #Use the list of crossings. Calculate max and min value between points
    #Difference from mean determines whether it is a top or bottom point
    extremes = []
    crossings = get_crossing_points(item_price, item_dates)
    last_crossing = -1
    for c in crossings:
        if last_crossing == -1:
            last_crossing = c
            continue

        curve_end = c[0]
        curve_start = last_crossing[0]
        min = np.min(item_price[curve_start:curve_end])
        max = np.max(item_price[curve_start:curve_end])
        is_top = last_crossing[2]
        value = max if is_top else min
        point = np.where(item_price[curve_start:curve_end] == value)
        point = point[0][0] + curve_start
        e = (point, value, is_top)
        extremes.append(e)

        last_crossing = c

    return extremes


# The number of times the price crossed the average price
def get_n_cross(item_price, item_dates, extremes, min_move):
    #min move is percent change required. eg 5% = 0.05
    avg = get_avg_line_num(item_price, item_dates)
    n_cross = 0
    for e in extremes:
        if not e[2]: # if bottom
            continue
        if e[1] >= avg*(min_move + 1):
            n_cross += 1


    return n_cross

#average price of top
def get_avg_top(item_price, item_dates, extremes, min_move):

    avg = get_avg_line_num(item_price, item_dates)
    tops = []

    for e in extremes:
        if not e[2]: # if bottom
            continue
        if e[1] >= avg*(min_move + 1):
            tops.append( e[1] )

    if not tops: return None
    return sum(tops)/len(tops)


def get_precedent(item_price, item_dates, extremes, price, margin):
    '''
    Returns two values

    * The number of times the price has moved from current price to a new local high (min +margin%)
    * The average percentage change in those moves.
    '''

    returns = []
    n_precedent = 0
    precedent_mode = False
    for e in extremes:
        if precedent_mode:
            if e[1] > price*(1+margin):
                n_precedent += 1
                returns.append( e[1]-price )
                precedent_mode = False
                continue

        if not e[2] and e[1] <= price:
            precedent_mode = True


    if n_precedent == 0:
        return None
    else:
        return n_precedent, (sum(returns)/n_precedent)/price

# The ratio between average price and current price
def get_mean_dif(item_price, item_dates):
    avg = get_avg_line_num(item_price, item_dates)
    current = get_current_price(item_price)
    dif = avg - current
    return dif/current

        

def plot_crossing_points(item_price, item_dates):
    plt_dates = matplotlib.dates.date2num(item_dates)

    crossings = get_crossing_points(item_price, item_dates)
    plot_avg_line(item_price, item_dates)
    plt.plot( plt_dates[ [c[0] for c in crossings] ], [c[1] for c in crossings], 'bo')

def plot_extreme_points(item_price, item_dates):
    plt_dates = matplotlib.dates.date2num(item_dates)

    extremes = get_extreme_points(item_price, item_dates)
    color_map = {False: 'r', True: 'g'}
    for e in extremes:
        plt.plot( plt_dates[e[0]], e[1], 'bo', color=color_map[e[2]] )


def calculate_features(item_data, RESUME_FROM_API_FAIL, margin):
    '''
    Calculates feature for all items in item_data by pulling price history and calling feature methods.
    '''

    total_iterations = len(item_data)
    if not RESUME_FROM_API_FAIL:
        current_iter = 0
        util_cache_store('current_iter', current_iter)
        feature_list_og = []
    else:
        iters_progress_skips = 0
        caught_up = False
        current_iter = util_cache_get('current_iter')
        print(f'Restarting after API failure: from iteration {current_iter}')

    utils.util_progress_start('Calculating item-features. Current item: ')
    for item in item_data.values():

        if RESUME_FROM_API_FAIL and not caught_up:
            if iters_progress_skips < current_iter:
                iters_progress_skips += 1
                continue
            else:
                caught_up = True

        prices, timestamps = get_data_for_id(item['id'])

        if len(prices) == 0:
            raise Exception('API failure, exiting. Restart manually at latest id.')

        period_pricing = util_get_period_pricing(prices, timestamps)

        #Check if no data for recent period
        skip_item = False
        for v in period_pricing.values():
            if len(v[0]) == 0:
                id_print = item['id']
                name_print = item['name']
                print(f'Skipped itemId {id_print}, {name_print}. No data for recent period.')
                skip_item = True
                break
        if skip_item:
            continue

        name = item['name']
        current_price = get_current_price(period_pricing['1month'][0])
        highest_1year = get_highest_1year_price(period_pricing['12month'][0], period_pricing['12month'][1])

        highest_period = []
        potential20 = []
        max_profit = []
        mean = []
        mean_dif = []
        n_precedent = []
        precedent_return = []
        n_cross = []
        avg_top = []
        for key in period_pricing:
            p, t = period_pricing[key]
            highest_period.append( get_highest_period(p) )
            potential20.append( get_potential20(p, t) )
            max_profit.append( get_max_profit(p, t) )
            mean.append( get_avg_line_num(p, t) )
            mean_dif.append( get_mean_dif(p, t) )

            extremes = get_extreme_points(p, t)
            precedent = get_precedent(p, t, extremes, current_price, margin)
            if precedent == None:
                n_precedent.append( 0 )
                precedent_return.append( 0 )
            else:
                n_precedent.append( precedent[0] )
                precedent_return.append( precedent[1] )

            n_cross.append( get_n_cross(p, t, extremes, margin) )
            avg_top.append( get_avg_top(p, t, extremes, margin) )
        
        f = FeatureSet(item['id'], name, period_pricing, current_price, highest_1year, highest_period, potential20, max_profit, mean, margin, n_cross, avg_top, n_precedent, precedent_return, mean_dif)
        feature_list_og.append(f)
        current_iter += 1
        util_cache_store('current_iter', current_iter)
        utils.util_progress_update(f'{name}. Progress: {round(100*current_iter/total_iterations, 1)}%')

    utils.util_progress_end()
    return feature_list_og


# Function to filter a feature_list. May sort it in the process
def f_filter(f_list, f_mode, percentile=-1, potential20=False, mean_dif=False):

    if mean_dif:
        f_list = [f for f in f_list if sum(f.mean_dif[0:3])/len(f.mean_dif[0:3]) >= mean_dif   ]

    if potential20:
        f_list = [f for f in f_list if f.potential20[3]]

    if f_mode != -1:
        for f in f_list:
            f.set_sorting_mode(f_mode)

    f_list = sorted(f_list)

    if percentile != -1:
        length = len(f_list)
        n_to_keep = int(length * (1 - percentile/100))
        n_to_keep = max(n_to_keep, 10)
        if n_to_keep < length:
            del f_list[0:length - n_to_keep]

    return f_list

def save_feature_list(f_list, FILTER_MODE, SORT_MODE, POTENTIAL20, PERCENTILE, top3=True):

    with open('best_feature_data.txt', 'w') as fp:
        fp.write(f'Summary of best items found using filter_mode={FILTER_MODE}, sort_mode={SORT_MODE}, p={PERCENTILE},'
        f'potential20={POTENTIAL20}. Found {len(f_list)} items.\n')

        for f in f_list:
            fp.write(f'\n\t{f.item}(id:{f.id}):\n')
            fp.write(f'price={f.price}\nmean={f.avg_line_num}\nmax_profit={f.max_profit}\nn_cross={f.n_cross}\n'
                f'mean_dif={f.mean_dif}\nn_predecent={f.n_precedent}\nprecedent_return={f.precedent_return}\npotential20={f.potential20}\n')
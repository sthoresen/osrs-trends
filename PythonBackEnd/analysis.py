from ipywidgets import IntProgress
from IPython.display import display
import datetime
from datetime import timedelta
import numpy as np

import api
import utils
import features


#INVESTMENT_SIZE = 15*1000*1000 #15m gp
VOLUME_SALE_LIMIT = 0.2 # Sell max this fraction of the volume myself.
PRICE_IMPACT_PER_LIMIT = 0.05 # Adjust the effective price downwards by this percentage

#Remove items with low liquidity or buy limits
def filter_junk(item_data, vol_req, buy_lim_req):
    #f = IntProgress(min=0, max=len(item_data)) # instantiate the bar
    #display(f) # display the bar
    data_len = len(item_data)
    utils.util_progress_start(f'Filtering junk. Items: {data_len} ')

    VOL_REQ = 8000000
    BUY_LIM_REQ = 2000000


    print(f"Length of dict pre junk-removal: {data_len}")

    items_removed_by_both_reqs = []
    items_removed_by_volume_req = []
    items_removed_by_buy_limit_req = []

    data_to_add = {}

    iters = -1
    for id, item_info in item_data.items():
        iters += 1
        progress = iters/data_len
        utils.util_progress_update(f'Progress: {round(progress*100, 1)}%. Detail: i {iters}/{data_len}')
        if 'limit' in item_info.keys():
            buy_limit = int(item_info["limit"])
        else: #Unkown buy limit
            buy_limit = -1

        vol, price = api.get_recent_vol_and_price(id)
        if price == None:
            name = item_info['name']
            print(f'Note: id{id} ({name}) was ignored, not in the API')
            items_removed_by_both_reqs.append(id)
            continue

        vol_24h = vol*price
        if buy_limit == -1:
            buy_limit_gp_max = BUY_LIM_REQ + 10
        else:
            buy_limit_gp_max = buy_limit * 6 * price

        if vol_24h < VOL_REQ and buy_limit_gp_max < BUY_LIM_REQ:
            items_removed_by_both_reqs.append(id)
        elif vol_24h < VOL_REQ:
            items_removed_by_volume_req.append(id)
        elif buy_limit_gp_max < BUY_LIM_REQ:
            items_removed_by_buy_limit_req.append(id)
        else:
            #Newer addition. Save the vol data along
            data_to_add[id] = vol_24h

    utils.util_progress_end()

    print(len(items_removed_by_both_reqs))
    print(len(items_removed_by_volume_req))
    print(len(items_removed_by_buy_limit_req))

    for i in range(3):
        for prints in range(10):
            if i == 0:
                list_name = "both"
                list = items_removed_by_both_reqs
            elif i == 1: 
                list_name = "volume"
                list = items_removed_by_volume_req
            elif i == 2: 
                list_name = "buy_lim"
                list = items_removed_by_buy_limit_req
            
            id = list[prints]
            item_name = item_data[id]['name']
            print(f"Req:\"{list_name}\" removed item_id {id}: {item_name}")


    data_no_junk = item_data.copy()

    for id in items_removed_by_both_reqs:
        data_no_junk.pop(id)

    for id in items_removed_by_volume_req:
        data_no_junk.pop(id)

    for id in items_removed_by_buy_limit_req:
        data_no_junk.pop(id)

    for id in data_no_junk.keys():
        data_no_junk[id]['vol_stable'] = data_to_add[id]

    return data_no_junk

def _get_exit_price_deprecated(p,t,target, date_start, date_end):
    #Return target price if it is found in date range. If not, return the last price at the end (insta-sell)
    # Note: return value is tuple: price, days until exit
    p_trimmed = []
    t_trimmed = []
    for i in range(len(t)):
        if t[i] < date_start:
            continue
        if t[i] > date_end:
            break
        p_trimmed.append(p[i])
        t_trimmed.append(t[i])

    for i in range(len(t_trimmed)):
        price = p_trimmed[i]
        if price >= target:
            return (price, (t_trimmed[i] - t_trimmed[0]).days + 1)

    # Insta sell: target not reached.
    return (p_trimmed[-1], (t_trimmed[-1] - t_trimmed[0]).days + 1)


def _get_exit_price(p, t, v, target, date_start, date_end, BANKROLL, name=None):
    # Start selling when the price reaches target
    # Limit sell orders to 20% of volume each day
    # If time reaches date_end, start selling maximum every day
    # Report the average sale price.
    p_trimmed = []
    t_trimmed = []
    v_trimmed = []
    real_time_position_size = BANKROLL * 1000 * 1000
    price_adj_factor = 1
    sales = [] #tuples: volume, price
    last_i = -1
    last_correct_vol = -1
    for i in range(len(t)):
        if t[i] < date_start:
            continue
        if t[i] > date_end:
            break
        p_trimmed.append(p[i])
        t_trimmed.append(t[i])
        v_trimmed.append(v[i])
        if last_correct_vol == -1 and v[i] != -1:
            last_correct_vol = v[i]
        last_i = i

    days_to_exit = -1

    for i in range(len(t_trimmed)):
        price = p_trimmed[i]
        if price*price_adj_factor >= target:
            #Initiate a sale
            total_v = v_trimmed[i]
            if total_v == -1:
                if last_correct_vol == -1:
                    print(f'not able to get volume data! date start end = {date_start}, {date_end}. Item={name}')
                    #raise Exception('Not able to get volume data!')
                    total_v = 1
                else:
                    total_v = last_correct_vol
            else:
                last_correct_vol = total_v

            sell_able = total_v*VOLUME_SALE_LIMIT*price*price_adj_factor
            #print(f'first_sell_able ={sell_able}')
            if sell_able >= real_time_position_size:
                #print(f'Able to exit all! pos={real_time_position_size}')
                sales.append((real_time_position_size, price*price_adj_factor))
                days_to_exit = (t_trimmed[i] - t_trimmed[0]).days + 1
                break
            else:
                #print(f'Only able to exit partially! pos={real_time_position_size}')
                sales.append((sell_able, price*price_adj_factor))
                real_time_position_size = real_time_position_size - sell_able
                price_adj_factor = price_adj_factor - PRICE_IMPACT_PER_LIMIT



    if days_to_exit == -1:
        #print(f'starting force sales!')
    # Was not able to sell in time. Start liquidating 20% of vol each day. Assume I can dump all on the 5th day if 
    # I still haven't sold, as the price adj factor is really punishing at that point
        for i in range(last_i+1, len(t)):
            price = p[i]
            total_v = v[i]
            sell_able = total_v*VOLUME_SALE_LIMIT*price*price_adj_factor
            if sell_able >= real_time_position_size:
                    sales.append((real_time_position_size, price*price_adj_factor))
                    days_to_exit = (t[i] - t_trimmed[0]).days + 1
                    break
            else:
                sales.append((sell_able, price*price_adj_factor))
                real_time_position_size = real_time_position_size - sell_able
                price_adj_factor = price_adj_factor - PRICE_IMPACT_PER_LIMIT

            if i >= last_i+5:
                #print(f'Forcing liquidating at the last possible day! Oops')
                sales.append((real_time_position_size, price*price_adj_factor))
                days_to_exit = (t[i] - t_trimmed[0]).days + 1
                break

    return (_get_avg_price(sales), days_to_exit)


def _get_avg_price(sales):
    '''
    sales = list of tuples: (volume, price)
    '''
    total_sales = sum(sale[0] for sale in sales)
    return sum((sale[0]/total_sales)*sale[1] for sale in sales)


'''
Simulate trading strategy back in time (in order to estimate expected returns later).
'''
def backtest(feature_list, EARLIEST_SIM_START, SIM_SPACING, MIN_DAYS_TRADED, LAST_SIM_DAY, BANKROLL, MARGIN):
   
    days_past = EARLIEST_SIM_START
    results = [] # list of tuples (f, score, actual backtest), backtest = (return, holding_time)
    dates_exhausted = False
    sim_date = datetime.datetime.today() - timedelta(days=days_past)
    dates_to_calc = (sim_date - LAST_SIM_DAY).days
    sim_date_start = sim_date
    utils.util_progress_start(f'Performing backtest from {sim_date} to {LAST_SIM_DAY}. Current day: ')
    while not dates_exhausted and sim_date > LAST_SIM_DAY:
        sim_date = datetime.datetime.today() - timedelta(days=days_past)

        progress =  ((sim_date_start - sim_date).days / dates_to_calc)*100
        date_print = sim_date.strftime('%d/%m/%Y')
        utils.util_progress_update(f'{date_print}. Progress: {round(progress, 1)}%')

        #feature/item loop
        for f in feature_list:
            period_pricing_adj = utils.util_adjust_period_pricing(f.period_pricing, sim_date)

            if period_pricing_adj == -1 or len(period_pricing_adj['24month'][0]) < MIN_DAYS_TRADED:
                continue

            crossings2y = features.get_crossing_points(period_pricing_adj['24month'][0], period_pricing_adj['24month'][1], MARGIN)
            crossings30d = features.get_crossing_points(period_pricing_adj['1month'][0], period_pricing_adj['1month'][1], MARGIN)
            score_2y = features.get_n_cross(crossings2y)
            score_30d = features.get_n_cross(crossings30d)

            if score_2y == None:
                score_2y = (0,0)
            if score_30d == None:
                score_30d = (0,0)

            score = score_2y + score_30d

            #Skip data point if potential20 and mean_dif doesn't work out
            if features.get_potential20(period_pricing_adj['12month'][0], period_pricing_adj['12month'][1], sim_date) == False:
                continue

            mean_dif_score = features.get_mean_dif(period_pricing_adj['1month'][0], period_pricing_adj['1month'][1]) 
            if mean_dif_score < 0:
                continue


            #calc backtest
            mean_line_1month = features.get_avg_line_num(period_pricing_adj['1month'][0], period_pricing_adj['1month'][1])
            
            day_after_range = period_pricing_adj['1month'][1][-1] + timedelta(days=1)
            day_cutoff = period_pricing_adj['1month'][1][-1] + timedelta(days=90)
            
            #print(f'Starting exit calc for item={f.item}')
            if len(BANKROLL) == 1:
                exit = _get_exit_price(f.period_pricing['all'][0], f.period_pricing['all'][1], f.period_pricing['all'][2], mean_line_1month, day_after_range, day_cutoff, BANKROLL, name=f.item,)
            else:
                exit = []
                for b in BANKROLL:
                    e = _get_exit_price(f.period_pricing['all'][0], f.period_pricing['all'][1], f.period_pricing['all'][2], mean_line_1month, day_after_range, day_cutoff, b, name=f.item)
                    exit.append(e)
            #print(f'finalized exit calc! result={exit}')

            results.append((f.item, score, exit, features.get_current_price(period_pricing_adj['1month'][0]), mean_line_1month, score_2y, score_30d, period_pricing_adj['1month'][1][-1], f.id))

        days_past += SIM_SPACING

    utils.util_progress_end()
    return results


'''
Multiple backtests with different bankrolls
'''
'''
def backtest_multi(feature_list, EARLIEST_SIM_START, SIM_SPACING, MIN_DAYS_TRADED, LAST_SIM_DAY, BANKROLLS):
   
    results = []
    loops = 1
    for roll in BANKROLLS:
        print(f'Performing backtest for bankroll {loops}/{len(BANKROLLS)}')
        r = backtest(feature_list, EARLIEST_SIM_START, SIM_SPACING, MIN_DAYS_TRADED, LAST_SIM_DAY, roll)
        results.append(r)
        loops = loops + 1

    return results
'''

def backtest_summary(backtested, DEBUG):
    '''
    Function that calculates the relationship between score and return of the backtesting, used for plotting.
    Toggleable printing.
    '''

    scores = []
    returns = []
    returns_per_score = []
    for r in backtested:
        scores.append(r[1])
        returns.append( min(round((r[2][0]-r[3])/r[3]*100,2), 100) )
        while len(returns_per_score) <= r[1]:
            returns_per_score.append([])
        returns_per_score[r[1]].append( min(round((r[2][0]-r[3])/r[3]*100,2), 100) )


    avg_per_score = np.zeros(len(returns_per_score))
    for i, r in enumerate(returns_per_score):
        if len(r) == 0:
            avg_per_score[i] = 0
        else:    
            avg_per_score[i] = sum(r)/len(r)

        if DEBUG:
            print(f'score of {i} avg: {avg_per_score[i]}, n={len(r)}')


    return (scores, returns, avg_per_score)


def current_day_rankings(feature_list, MARGIN):
    '''
    Rank all items by current day score (what items are hot investments right now!), and sort.
    '''

    current_day_rankings = []
    for f in feature_list:
        period_pricing = f.period_pricing
        crossings2y = features.get_crossing_points(period_pricing['24month'][0], period_pricing['24month'][1], MARGIN)
        crossings30d = features.get_crossing_points(period_pricing['1month'][0], period_pricing['1month'][1], MARGIN)
        score_2y = features.get_n_cross(crossings2y)
        score_30d = features.get_n_cross(crossings30d)

        if score_2y == None:
            score_2y = (0,0)
        if score_30d == None:
            score_30d = (0,0)

        score = score_2y + score_30d

        #Skip data point if potential20 and mean_dif doesn't work out
        if features.get_potential20(period_pricing['12month'][0], period_pricing['12month'][1]) == False:
            continue

        mean_dif_score = features.get_mean_dif(period_pricing['1month'][0], period_pricing['1month'][1]) 
        if mean_dif_score < 0:
            continue

        current_day_rankings.append( (score,f.item, f.id) )

    return sorted(current_day_rankings, key=lambda x: x[0], reverse=True)


def numerical_score_investment_profile(scores, returns, current_score):
    #Method to give a numerical scalar score to a scores, returns plot, given a current score.
    #Criteria: Use results for the current score and lower scores, until I have found data for 3 different scores with a combined sample size of at least 15.
    #Return mean value, as I think that is more stable than multiplicative return. Closer to expected return.
    #If criteria can't be reached, return None

    MIN_SAMPLE_SIZE = 15
    SCORE_WIDTH_REQ = 3

    sampled_returns = []
    sampled_s = []

    #Sort scores high to low and keep returns linked still, index to index
    paired = [x for x in sorted(zip(scores,returns), key=lambda pair: pair[0], reverse=True)]
    #print(paired)
    #print(type(paired))
    #print(len(paired))
    scores = list(zip(*paired))[0]
    returns = list(zip(*paired))[1]

    for i, s in enumerate(scores):
        if s <= current_score:
            if s not in sampled_s:
                if len(sampled_s) >= SCORE_WIDTH_REQ and len(sampled_returns) >= MIN_SAMPLE_SIZE:
                    break
                sampled_s.append(s)

            sampled_returns.append(returns[i])

    if len(sampled_s) < SCORE_WIDTH_REQ or len(sampled_returns) < MIN_SAMPLE_SIZE:
        return None

    return sum(sampled_returns)/len(sampled_returns)


def summary_table_current_day_rankings(current_day_rankings, backtested, item_data_no_junk, feature_list, bankroll_i=None):

    summary_table = []
    for fav in current_day_rankings:
        scores = []
        returns = []
        id = fav[2]
        for r in backtested:
            if r[-1] == id:
                scores.append(r[1])
                if bankroll_i is None:
                    returns.append( min(round((r[2][0]-r[3])/r[3]*100,2), 100) )
                else:
                    returns.append( min(round((r[2][bankroll_i][0]-r[3])/r[3]*100,2), 100) )


        #if len(scores) == 0:
        #    print(f'Empty score!')
        #    print(id)

        last_price = item_data_no_junk[id]['last']
        for f in feature_list:
            if f.id == id:
                median = f.avg_line_num[0]
                break

        if len(scores) != 0:
            num = numerical_score_investment_profile(scores, returns, fav[0])
        else:
            #No backtesting results for item (likely a new item)
            num = None
        
        summary_table.append((fav,num,last_price,median) )

    return sorted(summary_table, key=lambda x: x[1] if x[1] != None else -1000, reverse=True)

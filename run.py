import numpy as np
import datetime
import pickle
import os
import warnings
import matplotlib
matplotlib.use('Agg') # no UI backend
import matplotlib.pyplot as plt
import matplotlib.dates
import json
import history_bank.history_db as history_bank


import api
import analysis
import features

DEBUG = True
DATA_NO_JUNK_READ_ONLY = True
DB_REMOVE_OTHERS = False
FEATURE_LIST_READ_ONLY = False
#RESUME_FROM_API_FAIL = False # If calculate_features fails and you want to continue from where it failed instead of restarting
BACKTEST_READ_ONLY = True
BACKTEST_MULTI_BANKROLL_MODE = True
BANKROLLS = [1, 20, 100, 500, 10000] # In Millions
BANKROLL = 15 # If not multi mode


item_data = api.get_item_data()

with open(f'/home/sindre/osrs-trends/testdump.txt', 'w') as fp:
    for i in item_data.keys():
        fp.write(f'key={i}. value={item_data[i]}')

print(f'found item data with length {len(item_data)}')


VOL_REQ = 8000000
BUY_LIM_REQ = 2000000

force_collect = False
if DATA_NO_JUNK_READ_ONLY and not os.path.isfile('/home/sindre/osrs-trends/data_no_junk_backup.txt'):
    warnings.warn('Brief price history has to be collected because data_no_junk_backup.txt does not exist.', UserWarning )
    force_collect = True

if DATA_NO_JUNK_READ_ONLY and not force_collect:
    with open(f'/home/sindre/osrs-trends/data_no_junk_backup.txt', 'rb') as handle:
        item_data_no_junk = pickle.loads(handle.read())
    print(f'item_data_no_junk was restored with length {len(item_data_no_junk)} as DATA_NO_JUNK_READ_ONLY is {DATA_NO_JUNK_READ_ONLY}')
   
else:
    print(f"Length of dict pre junk-removal: {len(item_data)}")
    item_data_no_junk = analysis.filter_junk(item_data, VOL_REQ, BUY_LIM_REQ)
    print(f"Length of dict post junk-removal: {len(item_data_no_junk)}")
    with open(f'/home/sindre/osrs-trends/data_no_junk_backup.txt', 'wb') as handle:
        pickle.dump(item_data_no_junk, handle)

# Databank
history_bank.read(f'/home/sindre/osrs-trends/history_bank/databank_test.dat')
status = history_bank.status()
print(f'Status of databank: {status}')
if DB_REMOVE_OTHERS:
    history_bank.remove_others(item_data_no_junk) 
if status == 'missing':
    print(f'Databank is missing, it will have to be collected')
    history_bank.overwrite(item_data_no_junk)
elif status > 0:
    print(f'Databank will have to be updated, days missing = {status}')
    history_bank.update(status)

n = history_bank.include_more(item_data_no_junk)
print(f'Added {n} new items from item_data_no_junk')
history_bank.write(f'/home/sindre/osrs-trends/history_bank/databank_test.dat')

#Feature generation
force_collect = False
if FEATURE_LIST_READ_ONLY and not os.path.isfile('/home/sindre/osrs-trends/feature_list_backup.txt'):
    warnings.warn('Features need to gathered because feature_list_backup.txt does not exist.', UserWarning )
    force_collect = True

MARGIN = 0.05

if FEATURE_LIST_READ_ONLY and not force_collect:

    with open('/home/sindre/osrs-trends/feature_list_backup.txt', 'rb') as handle:
        feature_list_og = pickle.loads(handle.read())
    print(f'Restored feature list from file instead of recalculating')

else:
    #feature_list_og = features.calculate_features(item_data_no_junk, RESUME_FROM_API_FAIL, margin)
    feature_list_og = features.calculate_features(item_data_no_junk, MARGIN)
    with open('/home/sindre/osrs-trends/feature_list_backup.txt', 'wb') as handle:
        pickle.dump(feature_list_og, handle)


FILTER_MODE = 'n_cross'
SORT_MODE = 'n_cross'
PERCENTILE = 50
POTENTIAL20 = True
MEAN_DIF = 0.05


print(f'feature_list length pre filtering: {len(feature_list_og)}')
feature_list = features.f_filter(feature_list_og, FILTER_MODE, PERCENTILE, POTENTIAL20, MEAN_DIF)
print(f'feature_list length post filtering: {len(feature_list)}')

for f in feature_list:
    f.set_sorting_mode(SORT_MODE)
feature_list = sorted(feature_list)
features.save_feature_list(feature_list, FILTER_MODE, SORT_MODE, POTENTIAL20, PERCENTILE)


#Backtesting
force_collect = False

fn = '/home/sindre/osrs-trends/backtest_backup_multi.dat' if BACKTEST_MULTI_BANKROLL_MODE else '/home/sindre/osrs-trends/backtest_backup.dat'
b_arg = BANKROLLS if BACKTEST_MULTI_BANKROLL_MODE else [BANKROLL]

if BACKTEST_READ_ONLY and not os.path.isfile(fn):
#if BACKTEST_READ_ONLY and not Path('{fn}').is_file():
    warnings.warn(f'Backtesting need to be calculated because {fn} does not exist.', UserWarning )
    force_collect = True

if BACKTEST_READ_ONLY and not force_collect:
    with open(f'{fn}', 'rb') as handle:
        backtested = pickle.load(handle)
        print(f'Restored backtesting from file instead of recalculating')

else:
    EARLIEST_SIM_START = 100 # days past
    SIM_SPACING = 1 # Days between each timepoint to sim
    MIN_DAYS_TRADED = 365 # For new items, when to ignore for too little data
    LAST_SIM_DAY = datetime.datetime.fromtimestamp( 1537920000000 / 1e3) # Wednesday, 26 September 2018 00:00:00 (when volume got tracked)

    backtested = analysis.backtest(feature_list, EARLIEST_SIM_START, SIM_SPACING, MIN_DAYS_TRADED, LAST_SIM_DAY, b_arg, MARGIN)
    with open(f'{fn}', 'wb') as handle:
        pickle.dump(backtested, handle)

# Summarize backtesting results
if not BACKTEST_MULTI_BANKROLL_MODE:
    (scores, returns, avg_per_score) = analysis.backtest_summary(backtested, DEBUG)
    plt.plot(scores, returns, 'bo')
    plt.plot(scores, np.zeros(len(scores)), label='zero', color='black')
    plt.plot(np.arange( len(avg_per_score) ), avg_per_score, label='avg', color='red')
    plt.legend()
    plt.xlabel('score')
    plt.ylabel('return')
    plt.title('Backtesting general score-return analysis')
    plt.savefig('backtest_plot.png')


# And now, rank all items by current day score (what items are good investment based on current day score)
current_day_rankings = analysis.current_day_rankings(feature_list, MARGIN)




 #Summarize results in a table
if not BACKTEST_MULTI_BANKROLL_MODE:
    summary_table = analysis.summary_table_current_day_rankings(current_day_rankings, backtested, item_data_no_junk, feature_list)
    
    toj = {}
    with open(f'/home/sindre/osrs-trends/scoring.txt', 'w') as fp:
        for s in summary_table:
            if s[1] is None:
                ret = 'None'
            else:
                ret = f'{round(s[1],1)}%'
            print(f'{s[0]} expected_return: {ret}. Price: {s[2]}. Median: {s[3]}')
            fp.write(f'{s[0]} expected_return: {ret}. Price: {s[2]}. Median: {s[3]}\n')

            toj_id = int(s[0][2])
            if 'limit' in item_data_no_junk[toj_id]:
                lim = item_data_no_junk[toj_id]['limit']
            else:
                lim = 'unknown'

            toj[toj_id] = {'score': s[0][0], 'name': s[0][1], 'return': ret, 'price': s[2], 'median': int(s[3]), 'vol_stable': item_data_no_junk[toj_id]['vol_stable'], 'limit': lim}

    for e in toj[2355].values():
        print(f'element {e} is of type {type(e)}')

    with open(f'/home/sindre/osrs-trends/scoring.json', 'w') as fp:
        json.dump(toj,fp)
    print('Scoring is also saved to scoring.txt and scoring.json')

else:

    for i in range(len(BANKROLLS)):

        summary_table = analysis.summary_table_current_day_rankings(current_day_rankings, backtested, item_data_no_junk, feature_list, bankroll_i=i)
        toj = {}
        with open(f'/home/sindre/osrs-trends/scoring{BANKROLLS[i]}.txt', 'w') as fp:
            for s in summary_table:
                if s[1] is None:
                    ret = 'None'
                else:
                    ret = f'{round(s[1],1)}%'
                #print(f'{s[0]} expected_return: {ret}. Price: {s[2]}. Median: {s[3]}')
                fp.write(f'{s[0]} expected_return: {ret}. Price: {s[2]}. Median: {s[3]}\n')

                toj_id = int(s[0][2])
                if 'limit' in item_data_no_junk[toj_id]:
                    lim = item_data_no_junk[toj_id]['limit']
                else:
                    lim = 'unknown'

                toj[toj_id] = {'score': s[0][0], 'name': s[0][1], 'return': ret, 'price': s[2], 'median': int(s[3]), 'vol_stable': item_data_no_junk[toj_id]['vol_stable'], 'limit': lim}


        with open(f'/home/sindre/osrs-trends/scoring{BANKROLLS[i]}.json', 'w') as fp:
            json.dump(toj,fp)


        def is_json_serializable(data):
            try:
                json.dumps(data)
                return True
            except TypeError:
                return False

        with open(f'/home/sindre/osrs-trends/ChartDataOut.json', 'w') as fp:
            c = {}
            for f in feature_list:
                id = f.id
                name = f.item
                median = f.avg_line_num[4]
                price = f.price
                vol = item_data_no_junk[id]['vol_stable']
                if 'limit' in item_data_no_junk[id]:
                    lim = item_data_no_junk[id]['limit']
                else:
                    lim = 'unknown'
                n_cross = f.n_cross[4]
                p = f.period_pricing['24month'][0]
                t = f.period_pricing['24month'][1]
                labels = [i.timestamp() for i in t]
                #data = [int(i) for i in p]
                data = p.tolist()
                crossings = features.get_crossing_points(p,t,MARGIN)
                extremes = features.get_extreme_points(p,t, MARGIN)
                extremes = [(int(e[0]), int(e[1]), e[2]) for e in extremes]
                mean_dif = features.get_mean_dif(p,t)
                peak_dif = (features.get_highest_period(p) - price)/price

                c[id] = {'id': id, 'name': name, 'median': float(median), 'price': price, 'vol': vol, 'lim': lim,
                         'n_cross': n_cross, 'labels': labels, 'data': data, 'crossings': crossings, 'extremes': extremes,
                         'mean_dif': mean_dif, 'peak_dif': peak_dif}
                '''
                def is_json_serializable(data):
                    try:
                        json.dumps(data)
                        return True
                    except TypeError:
                        return False

                # Assuming c is your dictionary
                for id, item_data in c.items():
                    print(f"Checking item with id: {id}")
                    for key, value in item_data.items():
                        if not is_json_serializable(value):
                            print(f"Key '{key}' with value '{value}' is not JSON serializable.")
                '''

                

            json.dump(c,fp)



        
    print(f'Scoring is saved to scoring{{BANKROLL}}.txt and .json')
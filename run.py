import numpy as np
import datetime
import pickle
from pathlib import Path
import warnings
import matplotlib
matplotlib.use('Agg') # no UI backend
import matplotlib.pyplot as plt
import matplotlib.dates


import api
import analysis
import features

DEBUG = False
DATA_NO_JUNK_READ_ONLY = True
FEATURE_LIST_READ_ONLY = True
RESUME_FROM_API_FAIL = False # If calculate_features fails and you want to continue from where it failed instead of restarting
BACKTEST_READ_ONLY = True


item_data = api.get_item_data()

print(f'found item data with length {len(item_data)}')


VOL_REQ = 8000000
BUY_LIM_REQ = 2000000

force_collect = False
if DATA_NO_JUNK_READ_ONLY and not Path('./data_no_junk_backup.txt').is_file():
    warnings.warn('Brief price history has to be collected because data_no_junk_backup.txt does not exist.', UserWarning )
    force_collect = True

if DATA_NO_JUNK_READ_ONLY and not force_collect:
    with open(f'data_no_junk_backup.txt', 'rb') as handle:
        item_data_no_junk = pickle.loads(handle.read())
    print(f'item_data_no_junk was restored with length {len(item_data_no_junk)} as DATA_NO_JUNK_READ_ONLY is {DATA_NO_JUNK_READ_ONLY}')
   
else:
    print(f"Length of dict pre junk-removal: {len(item_data)}")
    item_data_no_junk = analysis.filter_junk(item_data, VOL_REQ, BUY_LIM_REQ)
    print(f"Length of dict post junk-removal: {len(item_data_no_junk)}")
    with open(f'data_no_junk_backup.txt', 'wb') as handle:
        pickle.dump(item_data_no_junk, handle)

force_collect = False
if FEATURE_LIST_READ_ONLY and not Path('./feature_list_backup.txt').is_file():
    warnings.warn('Features need to gathered because feature_list_backup.txt does not exist.', UserWarning )
    force_collect = True


if FEATURE_LIST_READ_ONLY and not force_collect:

    with open('feature_list_backup.txt', 'rb') as handle:
        feature_list_og = pickle.loads(handle.read())
    print(f'Restored feature list from file instead of recalculating')

else:
    margin = 0.05
    feature_list_og = features.calculate_features(item_data_no_junk, RESUME_FROM_API_FAIL, margin)
    with open('feature_list_backup.txt', 'wb') as handle:
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
if BACKTEST_READ_ONLY and not Path('./backtest_backup.dat').is_file():
    warnings.warn('Backtesting need to be calculated because backtest_backup.dat does not exist.', UserWarning )
    force_collect = True

if BACKTEST_READ_ONLY and not force_collect:
    with open(f'backtest_backup.dat', 'rb') as handle:
        backtested = pickle.load(handle)
        print(f'Restored backtesting from file instead of recalculating')

else:
    EARLIEST_SIM_START = 90 # days past
    SIM_SPACING = 1 # Days between each timepoint to sim
    MIN_DAYS_TRADED = 365 # For new items, when to ignore for too little data
    LAST_SIM_DAY = datetime.datetime.fromtimestamp( 1537920000000 / 1e3) # Wednesday, 26 September 2018 00:00:00 (when volume got tracked)

    backtested = analysis.backtest(feature_list, EARLIEST_SIM_START, SIM_SPACING, MIN_DAYS_TRADED, LAST_SIM_DAY)
    with open('backtest_backup.dat', 'wb') as handle:
        pickle.dump(backtested, handle)


# Summarize backtesting results

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
current_day_rankings = analysis.current_day_rankings(feature_list)

#Summarize results in a table
summary_table = analysis.summary_table_current_day_rankings(current_day_rankings, backtested, item_data_no_junk, feature_list)
with open('scoring.txt', 'w') as fp:
    for s in summary_table:
        if s[1] is None:
            ret = 'None'
        else:
            ret = f'{round(s[1],1)}%'
        print(f'{s[0]} expected_return: {ret}. Price: {s[2]}. Median: {s[3]}')
        fp.write(f'{s[0]} expected_return: {ret}. Price: {s[2]}. Median: {s[3]}\n')

print('Scoring is also saved to scoring.txt')

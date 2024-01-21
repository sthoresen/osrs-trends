from urllib.request import urlopen, Request
import json
import datetime
import statistics
import numpy as np
import pickle

import sys
#sys.path.append('../')
import os

import utils
import api

db = None

def status():

    if db == None or not db:
        return 'missing'
    
    # Get most recent timestamp from the api
    latest_api = api.get_latest_timestamp()

    # Find latest from db
    latest_db = db[453][1][-1]

    age_days = (latest_api - latest_db).days
    return age_days

def overwrite(items):


    current_iter = 0
    total_iterations = len(items)

    utils.util_progress_start('Rebuilding the databank. Current item and progress: ')


    global db
    db = {}
    for id in items.keys():
        name = items[id]['name']
        utils.util_progress_update(f'{name}. Progress: {round(100*current_iter/total_iterations, 1)}%')
        d = api.get_data_for_id(id)
        db[id] = d
        current_iter = current_iter + 1

    utils.util_progress_end()

def update(age):

    global db
    if db == None or not db:
        print('Databank cannot be updated - it is empty or not loaded')

    if age < 89:
        update_method = api.get_data_for_id_90d
    else:
        update_method = api.get_data_for_id



    utils.util_progress_start(f'Updating the database, with an age of {age}.')
    current_iter = 0
    total_iterations = len(db)
    utils.util_progress_update(f'Progress: {round(100*current_iter/total_iterations, 1)}%')

    last_db_entry = None

    for id in db.keys():
        d = update_method(id)
        last_db_entry = db[id][1][-1]

        #print(f'last_db_entry ={last_db_entry}')

        index_in_new = d[1].index(last_db_entry)

        #print(f'index_in_new ={index_in_new}')

        new_len = len(d[1])
        n_new_entries = new_len- index_in_new - 1

        new_prices = np.ones(n_new_entries).astype('int32')*-69
        new_vol = np.ones(n_new_entries).astype('int32')*-69

        for i in range(index_in_new+1, new_len):
            db[id][1].append(d[1][i])
            new_prices[i-index_in_new-1] = d[0][i]
            new_vol[i-index_in_new-1] = d[2][i]

        #print(type(db[id][0]))
        #print(db[id][0].shape)
        #cc =np.concatenate((db[id][0], d[0]))
        #print(f'concat = {cc}. type = {type(cc)}')
        #db[id][0] = np.concatenate((db[id][0], d[0]))
        #db[id][2] = np.concatenate((db[id][2], d[2]))

        #print(f'new prices ={new_prices}')
        #print(f'new vols ={new_vol}')


        db[id] = (np.concatenate((db[id][0], new_prices)), db[id][1] , np.concatenate((db[id][2], new_vol)))

        current_iter = current_iter + 1
        utils.util_progress_update(f'Progress: {round(100*current_iter/total_iterations, 1)}%')
        utils.util_progress_end()


    print(f'Updated the databank given age = {age}. Last stored date was {last_db_entry}. Updated latest => {db[453][1][-1]}')

def include_more(items):

    global db
    new_items = 0

    for id in items.keys():
        if id not in db:
            d = api.get_data_for_id(id)
            db[id] = d
            new_items = new_items + 1

    return new_items

def remove_others(item_data):
    if db == None or not db:
        return 
    
    removed = 0
    to_remove = []

    for id in db.keys():
        if id not in item_data.keys():
            removed += 1
            to_remove.append(id)

    for id in to_remove:
        del db[id]

    print(f'Removed {removed} previous items from the db')


def close():
    global db
    db = None


def read(filepath):
    global db
    with open(filepath, 'rb') as handle:
        db = pickle.loads(handle.read())


def write(filepath):
    with open(filepath, 'wb') as handle:
        pickle.dump(db, handle)

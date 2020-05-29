import pandas as pd
import numpy as np
from random import shuffle
import datetime as dt
import io
import requests
import yaml

import pymysql
import sqlalchemy

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from google.cloud import storage

tm_repl_dict = {
    'Broncos': 'Brisbane Broncos',
    'Bulldogs': 'Canterbury Bulldogs',
    'Cowboys': 'North QLD Cowboys',
    'Dragons': 'St George Dragons',
    'Eels': 'Parramatta Eels',
    'Knights': 'Newcastle Knights',
    'Panthers': 'Penrith Panthers',
    'Rabbitohs': 'South Sydney Rabbitohs',
    'Raiders': 'Canberra Raiders',
    'Roosters': 'Sydney Roosters',
    'Sea Eagles': 'Manly Sea Eagles',
    'Sharks': 'Cronulla Sharks',
    'Storm': 'Melbourne Storm',
    'Titans': 'Gold Coast Titans',
    'Warriors': 'New Zealand Warriors',
    'Wests Tigers': 'Wests Tigers'
}

def get_log_marg(row):
    marg = row.marg
    if marg == 0:
        return 0
    else:
        amt = np.log(np.abs(marg) + 1)
        return (marg / np.abs(marg)) * amt

def form_marg(df, end_point, date_sub=150, time_weight=60):
    builder = df[['m_order','h_tm','a_tm','log_marg']]
    start_date = end_point - date_sub
    builder = builder[(builder.m_order > start_date) & (builder.m_order <= end_point)]
    form = {team: 0 for team in builder['h_tm'].unique()}
    team_list = list(builder['h_tm'].unique())
    team_pos = [i for i in range(len(team_list))]
    error = 999
    while error > 1e-20:
        old_form = form.copy()
        shuffle(team_pos)
        for pos in team_pos:
            i = team_list[pos]
            team = i
            temp = builder[(builder['h_tm'] == team) | (builder['a_tm'] == team)]
            summer = 0
            divider = 0
            for index, row in temp.iterrows():
                weight = 1 / float(np.exp((end_point - row.m_order) / time_weight))
                divider += weight
                if row['h_tm'] == team:
                    summer += (form[row['a_tm']] + row.log_marg) * weight
                else:
                    summer += (form[row['h_tm']] - row.log_marg) * weight
            form[i] = summer / divider
        error = sum([(old_form[x] - form[x])**2 for x in team_list])
    return(form)

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def index():
    return render_template("index.html")

@app.route('/v1/nrlform', methods=['GET'])
def get_form():
    client = storage.Client()
    bucket = client.get_bucket('nrlform')
    blob = bucket.blob('form_data.json')
    df = blob.download_as_string()
    return df

@app.route('/v1/updateform', methods=['GET'])
def update_form():
    client = storage.Client()
    bucket = client.get_bucket('nrlform')
    blob = bucket.get_blob('form_data.json')
    old = blob.download_as_string()
    old = pd.read_json(old)

    with open('secrets.yaml', 'r') as stream:
        secrets = yaml.load(stream)

    username = secrets['db_uname']
    password = secrets['db_pass']
    address = secrets['db_address']

    db = sqlalchemy.create_engine('mysql+pymysql://{}:{}@{}'.format(username,password,address))
    conn = db.connect()

    df = pd.read_sql('select * from access_nrl_match where season > 2013',conn)
    conn.close()

    df['h_tm'] = df['h_tm'].map(tm_repl_dict)
    df['a_tm'] = df['a_tm'].map(tm_repl_dict)

    df['marg'] = df['h_pts'] - df['a_pts']
    df['log_marg'] = df.apply(get_log_marg, axis=1)
    df['dow'] = pd.to_datetime(df.mtc_date).dt.dayofweek.apply(lambda x: x - 1 if x > 1 else x + 6)
    df = df.sort_values('mtc_date')
    df.index = range(df.shape[0])

    df['m_order'] = df.year * 100 + df['rnd_number'] * 2

    if df['m_order'].max() == old['rnd_id'].max():
        old = old[old.rnd_id != old.rnd_id.max()]

    new_rnds = df[[False if x in old.rnd_id.unique() else True for x in df.m_order.unique()]].m_order.unique()
    new_rnds = new_rnds[new_rnds > 201500]

    if len(new_rnds) > 0:
        all_form = dict()
        for rnd_id in new_rnds:
            all_form[rnd_id] = form_marg(df, rnd_id, 150, 60)

        all_vals = []
        for key in all_form:
            temp = []
            for k2 in df['h_tm'].unique():
                temp.append(all_form[key][k2])
            all_vals.append(temp)

        all_vals = np.array(all_vals)

        data = []
        for k1 in all_form:
            for k2 in all_form[k1]:
                data.append([k1, k2, all_form[k1][k2]])

        out_df = pd.DataFrame(data, columns=['rnd_id','team','form'])

        out_df['round'] = (out_df.rnd_id % 100) / 2
        out_df['year'] = out_df.rnd_id // 100

        mean_lookup = dict(out_df.groupby('rnd_id').form.mean())
        out_df['form'] = out_df.apply(lambda row: row.form - mean_lookup[row.rnd_id], axis=1)

        out_df = pd.concat([old, out_df], 0)

        for yr in range(out_df.year.min() + 1, out_df.year.max() + 1):
            tmp = out_df[out_df.year == yr]
            if tmp['round'].min != 0:
                tmp2 = out_df[out_df.year == yr - 1]
                tmp2 = tmp2[tmp2['round'] == tmp2['round'].max()]
                tmp2['rnd_id'] = yr * 100
                tmp2['round'] = 0.0
                tmp2['year'] = yr
                out_df = pd.concat([out_df, tmp2], 0)

        out_df.drop_duplicates(subset=['rnd_id', 'team'], inplace=True)
        out_df = out_df.sort_values('rnd_id')
        out_df.index = range(out_df.shape[0])

        client = storage.Client()
        bucket = client.get_bucket('nrlform')
        blob = bucket.get_blob('form_data.json')

        out_json = out_df.to_json(orient='records')
        blob.upload_from_string(out_json)

        return 'Successfully updated dataset.'
    else:
        return 'No new data to update.'


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8001)

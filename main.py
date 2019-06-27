import pandas as pd
import numpy as np
from random import shuffle
import datetime as dt

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from google.cloud import storage

def get_log_marg(row):
    marg = row.marg
    if marg == 0:
        return 0
    else:
        amt = np.log(np.abs(marg) + 1)
        return (marg / np.abs(marg)) * amt

def form_marg(df, end_point, date_sub=150, time_weight=60):
    builder = df[['m_order','Home Team','Away Team','log_marg']]
    start_date = end_point - date_sub

    builder = builder[(builder.m_order > start_date) & (builder.m_order < end_point)]
    form = {team: 0 for team in builder['Home Team'].unique()}
    team_list = list(builder['Home Team'].unique())
    team_pos = [i for i in range(len(team_list))]
    error = 999
    while error > 1e-20:
        old_form = form.copy()
        shuffle(team_pos)
        for pos in team_pos:
            i = team_list[pos]
            team = i
            temp = builder[(builder['Home Team'] == team) | (builder['Away Team'] == team)]
            summer = 0
            divider = 0
            for index, row in temp.iterrows():
                weight = 1 / float(np.exp((end_point - row.m_order) / time_weight))
                divider += weight
                if row['Home Team'] == team:
                    summer += (form[row['Away Team']] + row.log_marg) * weight
                else:
                    summer += (form[row['Home Team']] - row.log_marg) * weight
            form[i] = summer / divider
        error = np.sum((np.array(list(old_form.values())) - np.array(list(form.values())))**2)
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
    df = pd.read_excel('http://www.aussportsbetting.com/historical_data/nrl.xlsx', skiprows=1)
    df = df[df.Date.dt.year > 2013].iloc[:, [0,1,2,3,4,5,6]]

    df['marg'] = df['Home Score'] - df['Away Score']
    df['log_marg'] = df.apply(get_log_marg, axis=1)
    df['year'] = df.Date.dt.year
    df['dow'] = df.Date.dt.dayofweek.apply(lambda x: x - 1 if x > 1 else x + 6)
    df = df.sort_values('Date')
    df.index = range(df.shape[0])

    rounds = []
    curr_rnd = 26
    curr_year = 2013
    last_dow = 7
    for index, row in df.iterrows():
        if row.year > curr_year:
            curr_year = row.year
            curr_rnd = 1
        elif row.dow < last_dow:
            curr_rnd += 1
        last_dow = row.dow
        rounds.append(curr_rnd)

    df['round'] = rounds
    df['m_order'] = df.year * 100 + df['round'] * 2

    all_form = dict()
    for year in range(2015,2020):
        for rnd in range(1, df[df.year == year]['round'].max()+2):
            all_form[year * 100 +(2*rnd)] = form_marg(df, year * 100+(2*rnd), 150, 60)

    all_vals = []
    for key in all_form:
        temp = []
        for k2 in df['Home Team'].unique():
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
    out_df.head()

    mean_lookup = dict(out_df.groupby('rnd_id').form.mean())
    out_df['form'] = out_df.apply(lambda row: row.form - mean_lookup[row.rnd_id], axis=1)

    client = storage.Client()
    bucket = client.get_bucket('nrlform')
    blob = bucket.get_blob('form_data.json')
    
    out_json = out_df.to_json(orient='records')
    blob.upload_from_string(out_json)

    return ('', 204)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=4008)
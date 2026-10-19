import pandas as pd
from pathlib import Path

# setup paths relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = BASE_DIR / 'raw_data'
DATA_DIR = BASE_DIR / 'data'

# calculate time from datetime to minutes from midnight
def datetime_to_minutes(datetime_series):
    dt = pd.to_datetime(datetime_series)
    return dt.dt.hour * 60 + dt.dt.minute

# 1. load trains dataset
input_train_file = RAW_DATA_DIR / 'train_data_2019.csv'
print(f"1. Loading data from {input_train_file}...")

# loading columns that we need
cols = [
    'date', 'train_id', 'from_id', 'to_id', 'scheduled_time', 
    'delay_minutes', 'status'
]
df = pd.read_csv(input_train_file, usecols=cols)

# deleting canceled trains
df = df[df['status'] != 'cancelled'].copy()

# calculating day of week (1 = Monday, 7 = Sunday)
df['date_dt'] = pd.to_datetime(df['date'])
df['day_of_week'] = df['date_dt'].dt.dayofweek + 1

# sorting by train and scheduled time
df['sched_dt'] = pd.to_datetime(df['scheduled_time'])
df = df.sort_values(by=['date', 'train_id', 'sched_dt']).reset_index(drop=True)

# calculating departure and arrival times in minutes
# previous stop scheduled time represents departure time for the segment
df['prev_sched_dt'] = df.groupby(['date', 'train_id'])['sched_dt'].shift(1)

# filter out self-loops (from_id == to_id)
train_edges = df[df['from_id'] != df['to_id']].dropna(subset=['sched_dt']).copy()

# calculate dep_time_min, arr_time_min, and duration_min
dep_dt = train_edges['prev_sched_dt'].fillna(train_edges['sched_dt'])
arr_dt = train_edges['sched_dt']

train_edges['dep_time_min'] = datetime_to_minutes(dep_dt)
train_edges['arr_time_min'] = datetime_to_minutes(arr_dt)

# calculate duration in minutes
duration = (arr_dt - dep_dt).dt.total_seconds() / 60.0
train_edges['duration_min'] = duration.apply(lambda x: x + 1440 if x < 0 else (x if x > 0 else 15.0))

# fill missing delay_minutes with 0
train_edges['delay_minutes'] = train_edges['delay_minutes'].fillna(0)

# 2. agregating scheduled lines and calculating delay
print("2. agregating scheduled lines and calculating delay...")

# agregating scheduled lines
grouped = train_edges.groupby(['from_id', 'to_id', 'day_of_week', 'train_id']).agg(
    train_count=('status', 'count'),
    dep_time_min=('dep_time_min', lambda x: int(x.mode()[0]) if not x.empty else int(x.mean())),
    arr_time_min=('arr_time_min', lambda x: int(x.mode()[0]) if not x.empty else int(x.mean())),
    duration_min=('duration_min', 'mean'),
    hist_avg_delay_min=('delay_minutes', 'mean'),
    hist_delay_prob=('delay_minutes', lambda x: (x > 15).mean())
).reset_index()

# filter nonregular trains (at least 3 occurrences)
regular_edges = grouped[grouped['train_count'] >= 3].copy()

# rename station columns to origin and dest
regular_edges = regular_edges.rename(columns={'from_id': 'origin', 'to_id': 'dest'})

# convert station IDs to string
regular_edges['origin'] = regular_edges['origin'].astype(int).astype(str)
regular_edges['dest'] = regular_edges['dest'].astype(int).astype(str)

# add tag for Neo4j
regular_edges['edge_type'] = 'TRAIN_RIDE'

# rounding numbers
regular_edges['duration_min'] = regular_edges['duration_min'].round(1)
regular_edges['hist_avg_delay_min'] = regular_edges['hist_avg_delay_min'].round(2)
regular_edges['hist_delay_prob'] = regular_edges['hist_delay_prob'].round(3)

# 3. control of integrity with nodes
# filter nodes that exist also in nodes_station.csv
node_file = DATA_DIR / 'nodes_station.csv'
try:
    existing_stations = set(pd.read_csv('node_file')['station_id'].astype(str))
    regular_edges = regular_edges[
        regular_edges['origin'].isin(existing_stations) & 
        regular_edges['dest'].isin(existing_stations)
    ]
except FileNotFoundError:
    print("Warning: File 'nodes_station.csv' not found, control of integrity will be skipped.")

# 4. formating and saving
# sorting columns
final_cols = [
    'origin', 'dest', 'day_of_week', 'dep_time_min', 'arr_time_min',
    'duration_min', 'hist_avg_delay_min', 'hist_delay_prob', 'train_id', 'edge_type'
]

output_df = regular_edges[final_cols]

# saving to CSV
output_file = DATA_DIR / 'edges_trains.csv'
output_df.to_csv(output_file, index=False)

print(f"\nDone! Final file '{output_file}' was succesfully generated.")
import pandas as pd

# calculate time from HHMM to minut from midnight
def hhmm_to_minutes(hhmm_series):
    hhmm = hhmm_series.fillna(0).astype(int)
    hours = hhmm // 100
    minutes = hhmm % 100
    return (hours * 60 + minutes) % 1440    # 1440 minutes is full day

# 1. load flights dataset
input_flight_file = 'flight_data_2024.csv'
print(f"1. Loading data from {input_flight_file}...")

# loading columns that we need
cols = [
    'origin', 'dest', 'day_of_week', 'op_unique_carrier', 'op_carrier_fl_num',
    'crs_dep_time', 'crs_arr_time', 'crs_elapsed_time', 'arr_delay', 'cancelled'
]
df = pd.read_csv(input_flight_file, usecols=cols)

# deleting canceled flights
df = df[df['cancelled'] == 0].copy()

# creating unique flight number
df['flight_num'] = df['op_unique_carrier'] + '_' + df['op_carrier_fl_num'].astype(str)

# recalculating times of arrival and departure
df['dep_time_min'] = hhmm_to_minutes(df['crs_dep_time'])
df['arr_time_min'] = hhmm_to_minutes(df['crs_arr_time'])

# 2. agregating scheduled lines and calculating delay
print("2. agregating scheduled lines and calculating delay...")

# agregating scheduled lines
grouped = df.groupby(['origin', 'dest', 'day_of_week', 'flight_num']).agg(
    flight_count=('cancelled', 'count'),
    dep_time_min=('dep_time_min', lambda x: int(x.mode()[0]) if not x.empty else int(x.mean())),
    arr_time_min=('arr_time_min', lambda x: int(x.mode()[0]) if not x.empty else int(x.mean())),
    duration_min=('crs_elapsed_time', 'mean'),
    hist_avg_delay_min=('arr_delay', 'mean'),
    hist_delay_prob=('arr_delay', lambda x: (x > 15).mean())
).reset_index()

# filter nonregular flights
regular_edges = grouped[grouped['flight_count'] >= 3].copy()

# add tag for Neo4j
regular_edges['edge_type'] = 'FLIGHT'

# rounding numbers
regular_edges['duration_min'] = regular_edges['duration_min'].round(1)
regular_edges['hist_avg_delay_min'] = regular_edges['hist_avg_delay_min'].round(2)
regular_edges['hist_delay_prob'] = regular_edges['hist_delay_prob'].round(3)

# 3. control of integrity with nodes
# filter nodes that exist also in nodes_airport.csv
try:
    existing_airports = set(pd.read_csv('nodes_airport.csv')['airport_id'])
    regular_edges = regular_edges[
        regular_edges['origin'].isin(existing_airports) & 
        regular_edges['dest'].isin(existing_airports)
    ]
except FileNotFoundError:
    print("Warning: File 'nodes_airport.csv' not found, control of integrity will be skipped.")

# 4. formating and saving
#sorting columns
final_cols = [
    'origin', 'dest', 'day_of_week', 'dep_time_min', 'arr_time_min',
    'duration_min', 'hist_avg_delay_min', 'hist_delay_prob', 'flight_num', 'edge_type'
]

output_df = regular_edges[final_cols]

# saving to CSV
output_file = 'edges_flights.csv'
output_df.to_csv(output_file, index=False)

print(f"\nDone! Final file '{output_file}' was succesfully generated.")
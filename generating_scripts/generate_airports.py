import pandas as pd
from pathlib import Path

# setup paths relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = BASE_DIR / 'raw_data'
DATA_DIR = BASE_DIR / 'data'

# 1. load flights dataset
input_flight_file = RAW_DATA_DIR / 'flight_data_2024.csv'
print(f"1. Loading data from {input_flight_file}...")

flights = pd.read_csv(
    input_flight_file,
    usecols=['origin', 'origin_city_name', 'origin_state_nm', 'dest', 'dest_city_name', 'dest_state_nm']
)

# 2. extraction of unique airports
print("2. Extracting unique airports...")

# unique departure airports
origins = flights[['origin', 'origin_city_name', 'origin_state_nm']].drop_duplicates()
origins.columns = ['airport_id', 'city', 'state']

# unique arrival airports
dests = flights[['dest', 'dest_city_name', 'dest_state_nm']].drop_duplicates()
dests.columns = ['airport_id', 'city', 'state']

# connect departures and arrivals and delete duplicities
airports = pd.concat([origins, dests]).drop_duplicates(subset=['airport_id'])
print(f"    -> Found {len(airports)} unique airports.")

# 3. dowloading GPS coordinates from OpenFlights
print("3. Dowloading GPS coordinates from OpenFlights...")
openflights_url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"

# defining header
ref_cols = ['id', 'name', 'city_ref', 'country', 'iata', 'icao', 'lat', 'lng', 'alt', 'tz', 'dst', 'tz_db', 'type', 'source']
ref_airports = pd.read_csv(openflights_url, header=None, names=ref_cols)

# filter
ref_airports = ref_airports[['iata', 'name', 'lat', 'lng']]

# 4. merge data
print("4. Merging airpots with GPS coordinates...")
merged = pd.merge(
    airports,
    ref_airports,
    left_on='airport_id',
    right_on='iata',
    how='left'
)

# add tag for Neo4j
merged['node_type'] = 'Airport'

# 5. formating and saving
#sorting columns
final_airports = merged[['airport_id', 'name', 'city', 'state', 'lat', 'lng', 'node_type']]

# delete airports without GPS coordinates
final_airports = final_airports.dropna(subset=['lat', 'lng'])

# saving to final CSV file
output_file = DATA_DIR / 'nodes_airport.csv'
final_airports.to_csv(output_file, index=False)

print(f"\nDone! Final file '{output_file}' was succesfully generated.")
import pandas as pd
import time
from geopy.geocoders import Nominatim

# 1. manually definned stations
MANUAL_STATIONS = {
    '38174': {'lat': 40.7615, 'lng': -74.0756, 'city': 'Secaucus', 'state': 'NJ'},        # Secaucus Lower Lvl
    '38187': {'lat': 40.7615, 'lng': -74.0756, 'city': 'Secaucus', 'state': 'NJ'},        # Secaucus Upper Lvl
    '100':   {'lat': 41.0968, 'lng': -74.0135, 'city': 'Nanuet', 'state': 'NY'},          # Nanuet
    '38081': {'lat': 40.8651, 'lng': -74.1978, 'city': 'Montclair', 'state': 'NJ'},       # Montclair State U
    '39635': {'lat': 40.9038, 'lng': -74.2570, 'city': 'Wayne', 'state': 'NJ'},           # Wayne-Route 23
    '135':   {'lat': 41.4339, 'lng': -74.1299, 'city': 'Salisbury Mills', 'state': 'NY'}, # Salisbury Mills-Cornwall
    '113':   {'lat': 41.4745, 'lng': -74.4533, 'city': 'Otisville', 'state': 'NY'},       # Otisville
}

# 2. load trains dataset
input_train_file = 'train_data_2019.csv'
print(f"1. Loading data from {input_train_file}...")

lines = pd.read_csv(
    input_train_file,
    usecols=['from_id', 'from', 'to_id', 'to']
)

# 3. extraction of unique stations
print("2. Extracting unique stations...")

# unique source stations
from_stations = lines[['from_id', 'from']].drop_duplicates().rename(columns={'from_id': 'station_id', 'from': 'name'})

# unique destination stations
to_stations = lines[['to_id', 'to']].drop_duplicates().rename(columns={'to_id': 'station_id', 'to': 'name'})

# connect source and destination and delete duplicities
stations = pd.concat([from_stations, to_stations]).drop_duplicates(subset=['station_id']).dropna(subset=['station_id'])
stations['station_id'] = stations['station_id'].astype(int).astype(str)

total_stations = len(stations)
print(f"    -> Found {total_stations} unique stations.")

# 4. dowloading GPS coordinates from OpenStreetMap
print("3. Dowloading GPS coordinates from OpenStreetMap...")
geolocator = Nominatim(user_agent="bachelor_thesis_routing_engine_v3")

lats, lngs, cities, states = [], [], [], []

def extract_clean_city(address_dict, raw_name):
    """Function to get whole name of city"""
    city = address_dict.get('city') or address_dict.get('town') or address_dict.get('village') or address_dict.get('suburb')
    if city:
        return city
    
    clean = raw_name
    for suffix in ['Penn Station', 'Station', 'Terminal', 'Upper Lvl', 'Lower Lvl', 'Rail Terminal', 'Transit Center', 'Route 17', 'Main St']:
        clean = clean.replace(suffix, '').strip()
    return clean if clean else raw_name

for idx, (_, row) in enumerate(stations.iterrows(), 1):
    s_id = str(row['station_id'])
    s_name = str(row['name'])
    
    # control, if station is in storage
    if s_id in MANUAL_STATIONS:
        m = MANUAL_STATIONS[s_id]
        lats.append(m['lat'])
        lngs.append(m['lng'])
        cities.append(m['city'])
        states.append(m['state'])
        print(f"   [{idx}/{total_stations}] MANUAL OK: {s_name} -> {m['lat']:.4f}, {m['lng']:.4f}")
        continue
    
    # preparing expression for geocoder
    if "Penn Station" in s_name and "New York" in s_name:
        query = "Penn Station, New York, NY"
    elif "Penn Station" in s_name and "Newark" in s_name:
        query = "Newark Penn Station, NJ"
    elif "Philadelphia" in s_name:
        query = "30th Street Station, Philadelphia, PA"
    else:
        query = f"{s_name} train station, USA"

    # retry mechanism pre Error 429 (Too Many Requests)
    attempts = 0
    success = False

    while attempts < 3 and not success:
        try:
            loc = geolocator.geocode(query, addressdetails=True, timeout=10)
            
            if not loc:
                loc = geolocator.geocode(f"{s_name}, New Jersey, USA", addressdetails=True, timeout=10)

            if loc:
                lats.append(loc.latitude)
                lngs.append(loc.longitude)
                
                addr = loc.raw.get('address', {})
                cities.append(extract_clean_city(addr, s_name))
                
                if "New York" in s_name or "Suffern" in s_name or "Port Jervis" in s_name:
                    states.append('NY')
                elif "Philadelphia" in s_name:
                    states.append('PA')
                else:
                    states.append('NJ')
                    
                print(f"   [{idx}/{total_stations}] OK: {s_name} -> {loc.latitude:.4f}, {loc.longitude:.4f}")
            else:
                print(f"   [{idx}/{total_stations}] Warning: {s_name} doesn't found coordinates")
                lats.append(None)
                lngs.append(None)
                cities.append(extract_clean_city({}, s_name))
                states.append('NJ')
            
            success = True # succesfull request processing

        except Exception as e:
            attempts += 1
            if "429" in str(e):
                print(f"   [{idx}/{total_stations}] Error 429: API overload. Waiting 5 seconds (Attempt {attempts}/3)...")
                time.sleep(5) # if we block it
            else:
                print(f"   [{idx}/{total_stations}] ERROR in the {s_name}: {e}")
                if attempts == 3:
                    lats.append(None)
                    lngs.append(None)
                    cities.append(extract_clean_city({}, s_name))
                    states.append('NJ')
                time.sleep(2)

    time.sleep(2)

stations['lat'] = lats
stations['lng'] = lngs
stations['city'] = cities
stations['state'] = states
stations['node_type'] = 'Station'

# 5. formating and saving
final_cols = ['station_id', 'name', 'city', 'state', 'lat', 'lng', 'node_type']
final_stations = stations[final_cols]

# saving to final CSV file
output_file = 'nodes_station.csv'
final_stations.to_csv(output_file, index=False)

print(f"\nDone! Final file '{output_file}' was succesfully generated.")
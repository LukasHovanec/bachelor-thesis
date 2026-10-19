import pandas as pd
from math import radians, cos, sin, asin, sqrt

# formula to calculate geographic distance in km between two lat/lng points
def haversine(lat1, lon1, lat2, lon2):
    R = 3671.0      # radius of earth

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return R * c

# 1. load airport and station nodes
print("1. Loading airport and station nodes...")

try:
    airports = pd.read_csv('nodes_airport.csv')
    stations = pd.read_csv('nodes_station.csv')
except FileNotFoundError as e:
    print(f"Error loading node files: {e}")
    exit(1)

# filter out nodes missing lat/lng coordinates
airports = airports.dropna(subset=['lat', 'lng']).copy()
stations = stations.dropna(subset=['lat', 'lng']).copy()

# 2. calculating nearest intermodal transfers (Top 2 nearest stations per airport)
print("2. Calculating nearest intermodal transfers per airport...")

transfers = []
MAX_TRANSFER_DISTANCE_KM = 50.0
TOP_STATIONS = 2               # keep only the 2 nearest station
TRANSFER_SPEED_KMH = 35.0

for _, apt in airports.iterrows():
    apt_id = str(apt['airport_id'])
    apt_lat, apt_lng = float(apt['lat']), float(apt['lng'])

    station_distances = []

    for _, stn in stations.iterrows():
        stn_id = str(stn['station_id'])
        stn_lat, stn_lng = float(stn['lat']), float(stn['lng'])

        dist = haversine(apt_lat, apt_lng, stn_lat, stn_lng)

        if dist <= MAX_TRANSFER_DISTANCE_KM:
            station_distances.append((stn_id, dist))

    # sort by distance and pick top K nearest stations
    station_distances.sort(key=lambda x: x[1])
    nearest_stations = station_distances[:TOP_STATIONS]

    for stn_id, dist in nearest_stations:
        # base transit time in minutes
        travel_time_min = (dist / TRANSFER_SPEED_KMH) * 60.0
        dist_rounded = round(dist, 2)

        # Station -> Airport (Train to Flight transfer)
        # needs 150 minutes (2.5 hours) buffer for check-in, TSA security, boarding...
        duration_to_apt = round(travel_time_min + 150.0, 1)
        transfers.append({
            'origin': stn_id,
            'dest': apt_id,
            'distance_km': dist_rounded,
            'duration_min': duration_to_apt,
            'edge_type': 'TRANSFER_TO_AIRPORT'
        })

        # Airport -> Station (Flight to Train transfer)
        # Needs 60 minutes (1 hour) buffer for deboarding, baggage claim...
        duration_to_stn = round(travel_time_min + 60.0, 1)
        transfers.append({
            'origin': apt_id,
            'dest': stn_id,
            'distance_km': dist_rounded,
            'duration_min': duration_to_stn,
            'edge_type': 'TRANSFER_TO_STATION'
        })

transfers_df = pd.DataFrame(transfers)

# 3. formatting and saving
print("3. Formatting and saving transfers...")

final_cols = ['origin', 'dest', 'distance_km', 'duration_min', 'edge_type']
output_df = transfers_df[final_cols]

# saving to CSV
output_file = 'edges_transfers.csv'
output_df.to_csv(output_file, index=False)

print(f"\nDone! Final file '{output_file}' with {len(output_df)} transfer edges was successfully generated.")
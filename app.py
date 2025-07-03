from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import time
from datetime import datetime

app = Flask(__name__)

URL = "https://busvarna.com/onebusaway-api-webapp/siri/vehicle-monitoring"
API_KEY = "OBAKEY"

def get_data(line_number):
    params = {
        "key": API_KEY,
        "callback": "cb",
        "_": str(int(time.time() * 1000)),
        "OperatorRef": "TASRUD",
        "LineRef": line_number,
        "type": "json"
    }
    try:
        res = requests.get(URL, params=params)
        jsonp = res.text
        json_str = re.search(r"^[^(]+\((.*)\)$", jsonp).group(1)
        return json.loads(json_str)
    except Exception as e:
        print(f"Error fetching data for line {line_number}: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_buses')
def get_buses():
    results = {}
    
    for line in range(1, 101):
        data = get_data(line)
        if not data:
            continue
            
        try:
            delivery = data["Siri"]["ServiceDelivery"]["VehicleMonitoringDelivery"][0]
            vehicles = delivery.get("VehicleActivity", [])
            if vehicles:
                name = vehicles[0]["MonitoredVehicleJourney"]["PublishedLineName"]
                results[name] = vehicles
        except Exception as e:
            print(f"Error processing line {line}: {str(e)}")
            continue
        
        time.sleep(0.1)
    
    formatted_results = []
    for line_name, vehicles in results.items():
        line_data = {
            "line": line_name,
            "vehicles": []
        }
        
        for v in vehicles:
            mvj = v["MonitoredVehicleJourney"]
            call = mvj.get("MonitoredCall", {})
            extensions = call.get("Extensions", {}).get("Distances", {})
            
            # Calculate time until arrival if available
            arrival_time = None
            if call.get("ExpectedArrivalTime"):
                try:
                    arrival_dt = datetime.strptime(call["ExpectedArrivalTime"], "%Y-%m-%dT%H:%M:%S.%f%z")
                    now = datetime.now(arrival_dt.tzinfo)
                    mins_until_arrival = max(0, int((arrival_dt - now).total_seconds() / 60))
                    arrival_time = f"{mins_until_arrival} min"
                except:
                    arrival_time = call["ExpectedArrivalTime"]
            
            vehicle_data = {
                "vehicle_id": mvj['VehicleRef'],
                "destination": mvj['DestinationName'],
                "origin": mvj.get('OriginRef', ''),
                "direction": mvj.get('DirectionRef', ''),
                "location": {
                    "latitude": mvj['VehicleLocation']['Latitude'],
                    "longitude": mvj['VehicleLocation']['Longitude'],
                    "bearing": mvj.get('Bearing', 0)
                },
                "status": {
                    "monitored": mvj.get('Monitored', False),
                    "progress_rate": mvj.get('ProgressRate', ''),
                    "deviation": call.get("Extensions", {}).get("Deviation", "0")
                },
                "call": {
                    "stop_name": call.get("StopPointName", ""),
                    "presentable_distance": extensions.get("PresentableDistance", ""),
                    "distance_from_call": extensions.get("DistanceFromCall", 0),
                    "stops_from_call": extensions.get("StopsFromCall", 0),
                    "arrival_time": arrival_time
                },
                "recorded_time": v.get('RecordedAtTime', '')
            }
            line_data["vehicles"].append(vehicle_data)
        
        formatted_results.append(line_data)
    
    return jsonify(formatted_results)

if __name__ == '__main__':
    app.run(debug=True)

import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# CONFIGURATION
DATA_FOLDER = 'data'  # Make sure this matches your Docker volume or local path

def load_data(start_dt, end_dt):
    """
    Scans the data folder for files matching 'sensor_YYYYMMDD_HHMMSS.json'
    and loads those that fall within the requested time window.
    """
    combined_data = []
    
    # 1. Get all files in the folder
    if not os.path.exists(DATA_FOLDER):
        print(f"Warning: Folder {DATA_FOLDER} does not exist.")
        return []
        
    all_files = os.listdir(DATA_FOLDER)
    relevant_files = []

    # 2. Filter files based on the date in the filename
    # We look for files starting from (start_date - 1 day) to handle files 
    # that started yesterday but contain data for today.
    search_start_date = (start_dt - timedelta(days=1)).date()
    search_end_date = end_dt.date()

    for filename in sorted(all_files):
        # Expecting format: sensor_20251120_214032.json
        if filename.startswith('sensor_') and filename.endswith('.json'):
            try:
                # Extract the date part (e.g., "20251120")
                # Split by '_' gives: ['sensor', '20251120', '214032.json']
                date_part = filename.split('_')[1]
                file_date = datetime.strptime(date_part, "%Y%m%d").date()

                # Check if this file is within our interest window
                if search_start_date <= file_date <= search_end_date:
                    relevant_files.append(filename)
            except (IndexError, ValueError) as e:
                # Skip files that don't match the expected format
                print(f"Error: {e} - Skipping unrecognized file format: {filename}")
                continue

    # 3. Load data from identified files
    for filename in relevant_files:
        filepath = os.path.join(DATA_FOLDER, filename)
        try:
            with open(filepath, 'r') as f:
                day_data = json.load(f)
                combined_data.extend(day_data)
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    # 4. Filter exact data points by timestamp
    filtered_data = []
    for entry in combined_data:
        try:
            # Parse timestamp from JSON content: "2025-11-20T21:40:32Z"
            entry_ts = datetime.strptime(entry['ts'], "%Y-%m-%dT%H:%M:%SZ")
            # Keep only points strictly within the requested range
            if start_dt <= entry_ts <= end_dt:
                print(f"Adding entry with timestamp {entry_ts}")
                filtered_data.append(entry)
        except ValueError:
            print(f"Invalid timestamp format in entry: {entry}")
            continue
            
    # Sort by timestamp to ensure the chart draws lines correctly
    filtered_data.sort(key=lambda x: x['ts'])
            
    return filtered_data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get_readings')
def get_readings():
    time_range = request.args.get('range', '24h')
    ref_date_str = request.args.get('date')

    # Calculate End Time
    if ref_date_str:
        end_time = datetime.strptime(ref_date_str, "%Y-%m-%d")
        if end_time.date() == datetime.today().date():
            end_time = datetime.utcnow()
        else:
            end_time = end_time.replace(hour=23, minute=59, second=59)
    else:
        end_time = datetime.utcnow()

    # Calculate Start Time
    if time_range == '6h':
        start_time = end_time - timedelta(hours=6)
    elif time_range == '12h':
        start_time = end_time - timedelta(hours=12)
    elif time_range == '24h':
        start_time = end_time - timedelta(hours=24)
    elif time_range == '3d':
        start_time = end_time - timedelta(days=3)
    elif time_range == '7d':
        start_time = end_time - timedelta(days=7)
    elif time_range == '1m':
        start_time = end_time - timedelta(days=30)
    else:
        start_time = end_time - timedelta(hours=24)

    data = load_data(start_time, end_time)
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
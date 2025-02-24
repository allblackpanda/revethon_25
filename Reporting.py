from flask import Flask, render_template, request, jsonify
import pandas as pd
import requests, argparse
import json
import plotly.express as px
from datetime import datetime

PORT = 5000
CONFIG_FILE = "config.json"
LOG_FILE = "rate_table_editor.log"

def read_config():
    """Reads configuration from a file and returns it as a dictionary."""
    try:
        with open(CONFIG_FILE, 'r') as file:
            json_file = json.load(file)
            selected_config = json_file[config_parameter]
            return selected_config
    except ValueError:
        return f"Error: Config option {config} not found in file"
    except FileNotFoundError:
        return f"Error: File not found at path: {CONFIG_FILE}"
    except json.JSONDecodeError:
        return "Error: Invalid JSON format in file"

def fetch_data(number_days, environment):
    base_url = f"https://{config['site']}"
    if environment == "uat":
        base_url += "-uat"
    url = f"{base_url}.flexnetoperations.{config['geo']}/data/api/v1/report/usage"
    
    basic_Auth = config["basic_Auth"]
    headers = {"Authorization": f"Basic {basic_Auth}", "Content-Type": "application/json"}

    params = {
        "mode": "batch",
        "format": "json",
        "pastDays": number_days,
        "meterType": "elastic"
    }
    try:
        response = requests.get(url=url, headers=headers, params=params)
        if response.status_code in [200, 201]:
            return response.json().get("data", [])
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
    return []

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data', methods=['POST'])
def get_data():
    number_days = request.json.get('number_days', 3)
    environment = request.json.get('environment', 'uat')
    data = fetch_data(number_days, environment)
    df = pd.DataFrame(data)
    
    if not df.empty:
        # Handle empty values in usageTime
        df["usageTime"] = df["usageTime"].fillna(0)
        df["usageTime"] = df["usageTime"].astype(float) / 1000
        df["usageTime"] = df["usageTime"].apply(lambda x: datetime.utcfromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        
        # Handle empty values in used and meterQuantity
        df["used"] = pd.to_numeric(df["used"], errors='coerce').fillna(0).round(2)
        df["meterQuantity"] = pd.to_numeric(df["meterQuantity"], errors='coerce').fillna(0).round(2)
        
        df = df.sort_values(by="usageTime", ascending=True)
        account_options = df["accountId"].unique().tolist()
    else:
        account_options = []

    # Include the site information from config
    return jsonify({
        'accounts': account_options, 
        'data': df.to_dict(orient='records'),
        'site': config.get('site', '')
    })

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-config', "--config", help="Specify the configuration to override default config.json file", default='default')
    args = parser.parse_args()
    config_parameter = args.config
    config = read_config()
    port = config["port"] if "port" in config else PORT
    app.run(debug=True, port=port)
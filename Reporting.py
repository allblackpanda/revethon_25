from flask import Flask, render_template, request, jsonify
import pandas as pd
import requests, argparse
import json
import logging
from datetime import datetime

PORT = 5000
CONFIG_FILE = "config.json"
LOG_FILE = "rate_table_editor.log"

# Set up logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filemode='a'  # 'a' for append mode, which adds to existing file
)
logger = logging.getLogger(__name__)

def read_config():
    """Reads configuration from a file and returns it as a dictionary."""
    try:
        with open(CONFIG_FILE, 'r') as file:
            json_file = json.load(file)
            selected_config = json_file[config_parameter]
            logger.info(f"Configuration loaded successfully: {config_parameter}")
            return selected_config
    except ValueError:
        error_msg = f"Error: Config option {config_parameter} not found in file"
        logger.error(error_msg)
        return error_msg
    except FileNotFoundError:
        error_msg = f"Error: File not found at path: {CONFIG_FILE}"
        logger.error(error_msg)
        return error_msg
    except json.JSONDecodeError:
        error_msg = "Error: Invalid JSON format in file"
        logger.error(error_msg)
        return error_msg

def fetch_data(number_days, environment):
    logger.info(f"Fetching data for {number_days} days in {environment} environment")
    base_url = f"https://{config['site']}"
    if environment == "uat":
        base_url += "-uat"
    url = f"{base_url}.flexnetoperations.{config['geo']}/data/api/v1/report/usage"
    
    basic_Auth = config["basic_Auth"]
    headers = {"Authorization": f"Basic {basic_Auth}", "Content-Type": "application/json"}
    page_number = 1
    all_data = []
    params = {
        "mode": "batch",
        "format": "json",
        "pastDays": number_days,
        "meterType": "elastic",
        "pageNumber": page_number
        
    }
    try:
        logger.info(f"Fetching page {page_number} of data from {url}")
        response = requests.get(url=url, headers=headers, params=params)
        if response.status_code in [200, 201]:
            data = response.json().get("data", [])
            logger.info(f"Retrieved {len(data)} records from page {page_number}")
            
            while data: # Keep fetching data until there is no more data
                all_data.extend(data)
                page_number += 1
                params["pageNumber"] = page_number
                logger.info(f"Fetching page {page_number} of data")
                response = requests.get(url=url, headers=headers, params=params)
                data = response.json().get("data", [])
                logger.info(f"Retrieved {len(data)} records from page {page_number}")
                
            logger.info(f"Total records fetched: {len(all_data)}")
            return all_data
        else:
            logger.error(f"API request failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
    except Exception as e:
        error_msg = f"Error fetching data: {str(e)}"
        logger.error(error_msg)
        print(error_msg)
    return []

app = Flask(__name__)

@app.route('/')
def index():
    logger.info("Main page accessed")
    return render_template('index.html')

@app.route('/data', methods=['POST'])
def get_data():
    logger.info("Data endpoint accessed")
    number_days = request.json.get('number_days', 3)
    environment = request.json.get('environment', 'uat')
    logger.info(f"Request parameters: number_days={number_days}, environment={environment}")
    
    data = fetch_data(number_days, environment)
    df = pd.DataFrame(data)
    
    if not df.empty:
        logger.info(f"Processing {len(df)} records")
        # Handle empty values in usageTime
        df["usageTime"] = df["usageTime"].fillna(0)
        df["usageTime"] = df["usageTime"].astype(float) / 1000
        df["usageTime"] = df["usageTime"].apply(lambda x: datetime.utcfromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        
        # Handle empty values in used and meterQuantity
        df["used"] = pd.to_numeric(df["used"], errors='coerce').fillna(0).round(2)
        df["meterQuantity"] = pd.to_numeric(df["meterQuantity"], errors='coerce').fillna(0).round(2)
        
        df = df.sort_values(by="usageTime", ascending=True)
        account_options = df["accountId"].unique().tolist()
        logger.info(f"Found {len(account_options)} unique accounts")
    else:
        logger.warning("No data returned from API")
        account_options = []

    # Include the site information from config
    response_data = {
        'accounts': account_options, 
        'data': df.to_dict(orient='records'),
        'site': config.get('site', '')
    }
    logger.info("Data processed and returned successfully")
    return jsonify(response_data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-config', "--config", help="Specify the configuration to override default config.json file", default='default')
    args = parser.parse_args()
    config_parameter = args.config
    
    logger.info(f"Starting application with config parameter: {config_parameter}")
    config = read_config()
    
    port = config["port"] if "port" in config else PORT
    logger.info(f"Server starting on port {port}")
    
    app.run(debug=False, port=port)
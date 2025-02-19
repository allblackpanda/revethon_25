from flask import Flask, render_template, request, jsonify
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime

PORT = 5000
def read_config():
    """Reads configuration from a file and returns it as a dictionary."""
    config = {}
    with open("config.txt", "r") as file:
        for line in file:
            line = line.strip()
            if "=" in line:
                key, value = line.split(" = ", 1)  # Ensure splitting only on the first occurrence
                if key in ["accountid_exclude_uat", "accountid_exclude_prod"]:
                    config[key] = value.split(",")  # Convert comma-separated values into a list
                else:
                    config[key] = value
    return config

def fetch_data(number_days):
    config = read_config()
    url = f"https://{config['site']}-uat.flexnetoperations.{config['geo']}/data/api/v1/report/usage"
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
    data = fetch_data(number_days)
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

    return jsonify({'accounts': account_options, 'data': df.to_dict(orient='records')})

if __name__ == '__main__':
    config = read_config()
    port = config["port"] if "port" in config else PORT
    app.run(debug=True, port=port)
#Reason Codes - 7 Insufficient Feature Count
#Reason Codes - 15 Feature Unavailable
#Reason Codes - 67 Feature unavailable, checkout filter rejection
#Reason Codes - 11 Feature Expired
#Reason Codes - 12 Feature Version not Found
# response_codes = {
#     7: "Insufficient Feature Count",
#     15: "Feature Unavailable",
#     67: "Feature unavailable, checkout filter rejection",
#     11: "Feature Expired",
#     12: "Feature Version not Found"
# }
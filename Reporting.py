import json
import pandas as pd
import dash
import requests
from dash import dcc, html, Input, Output, State, ctx
import plotly.express as px
from datetime import datetime

def read_config():
    config = {}
    with open("config.txt", "r") as file:
        for line in file:
            key, value = line.strip().split(" = ")
            config[key] = value
    return config

# Function to fetch data from REST API
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

# Initialize Dash app
app = dash.Dash(__name__)

# Layout
app.layout = html.Div([
    html.Div([
        html.Label("# Past Days"),
        dcc.Input(
            id='num-days',
            type='number',
            value=3,
            min=1,
            step=1,
            debounce=True,
            placeholder="Enter number of days"
        ),
        html.Button('Refresh Data', id='refresh-button', n_clicks=0)
    ], style={'display': 'flex', 'justify-content': 'flex-end', 'gap': '10px'}),
    html.Div(id='loading', children="", style={'display': 'none', 'fontWeight': 'bold', 'color': 'blue'}),
    html.Label("Select Customer Account"),
    dcc.Dropdown(id='account-dropdown', placeholder="Select an Account"),
    dcc.Graph(id='line-chart'),
    html.Div(id='data-output')
])

@app.callback(
    [
        Output('account-dropdown', 'options'),
        Output('line-chart', 'figure'),
        Output('loading', 'children'),
        Output('loading', 'style'),
        Output('data-output', 'children')
    ],
    [
        Input('refresh-button', 'n_clicks'),
        Input('account-dropdown', 'value')
    ],
    State('num-days', 'value')
)
def update_data(n_clicks, selected_account, number_days):
    # Set loading state
    if n_clicks > 0:
        loading_message = "Loading..."
        style = {'display': 'block', 'fontWeight': 'bold', 'color': 'blue'}
    else:
        loading_message = ""
        style = {'display': 'none'}
    
    # Fetch data
    data = fetch_data(number_days)
    global df
    df = pd.DataFrame(data)
    
    if not df.empty:
        df["usageTime"] = df["usageTime"].astype(float) / 1000
        df["usageTime"] = df["usageTime"].apply(lambda x: datetime.utcfromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        df["used"] = df["used"].astype(float).round(2)
        
        # Sort data from oldest to newest by usageTime
        df = df.sort_values(by="usageTime", ascending=True)
        
        account_options = [{'label': acc, 'value': acc} for acc in df["accountId"].unique()]
    else:
        account_options = []
    
    # Handle filtering based on selected account
    if selected_account:
        filtered_df = df[df["accountId"] == selected_account]
    else:
        filtered_df = df

    # Generate figure
    fig = px.line(filtered_df, x="usageTime", y="used", markers=True, title="Usage Over Time") if not filtered_df.empty else px.line()
    
    # Set data output
    data_output = "Filtered data displayed." if selected_account else "Please select an account."
    
    # Reset loading message
    loading_message = ""  
    style = {'display': 'none'}
    
    return account_options, fig, loading_message, style, data_output

if __name__ == '__main__':
    app.run_server(debug=True)

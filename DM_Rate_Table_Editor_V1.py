import tkinter as tk
from tkinter import messagebox, Toplevel, Text, Scrollbar, ttk
from PIL import Image, ImageTk
from tkcalendar import Calendar
import time
import requests
import json
import datetime
import subprocess
import threading
import webbrowser
import argparse
import logging
import traceback
import re
import uuid
from io import BytesIO
import ttkbootstrap as ttkb
from ttkbootstrap.dialogs import DatePickerDialog
from ttkbootstrap import Button
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import socket

UAT_OPTION = "-uat"
REPORTING_APP_URL = "127.0.0.1"
PORT = 5000
PERMANENT_EPOCH = 253402300799999
ICON = "Revethon2025.ico"
FONT = ("Arial", 10, "normal")
CONFIG_FILE = "config.json"
LOG_FILE = "rate_table_editor.log"
EXAMPLE_RATE_TABLE = [{
    "effectiveFrom": "",
    "series": "NewSeries",
    "version": "1",
    "items": [
        {"name": "Intermediate", "version": "1.0", "rate": 7.0},
        {"name": "Basic", "version": "1.0", "rate": 5.0},
        {"name": "Advanced", "version": "1.0", "rate": 10.0}
    ]
}]

series_window = None  # Global variable to track the rate table window

####################################################################################
# Create command line argument options
parser = argparse.ArgumentParser()
parser.add_argument('-config', "--config", help="Specify the configuration to override default config.json file", default="default")
# Get what was passed if anything
args = parser.parse_args()
config_parameter = args.config

# Add logging
# Configure logging
logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_function_call(func):
    """Decorator to log function calls and their results."""
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            logging.info(f"Called: {func.__name__} | Args: {args}, Kwargs: {kwargs} | Result: {result}")
            return result
        except Exception as e:
            logging.error(f"Error in {func.__name__} at line {traceback.extract_tb(e.__traceback__)[-1][1]}: {e}")
            raise e
    return wrapper



def read_config():
    """Reads configuration from a file and returns it as a dictionary."""
    try:
        with open(CONFIG_FILE, 'r') as file:
            json_file = json.load(file)
            selected_config = json_file[config_parameter]
        try:
            with open(selected_config['jwt'], 'r') as jwt_file:
                jwt = jwt_file.read().strip()
                selected_config['jwt'] = jwt
            return selected_config
        except Exception as f:
            logging.error(f"Error reading JWT File: {f}")
            return {}
    except Exception as e:
        logging.error(f"Error reading config: {e}")
        return {}

def build_base_url():
    base_url = f"https://{config['site']}"
    if env_var.get() == UAT_OPTION:
        base_url += "-uat"
    base_url += f".flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0"
    return base_url
    
def build_api_headers():
    headers = {
        "Authorization": f"Bearer {config['jwt']}",
        "Content-Type": "application/json"
    }
    return headers

@log_function_call
def load_json(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        logging.error(f"Error loading JSON: {e}")
        return None

@log_function_call
def convert_epoch_to_date(epoch_ms):
    try:
        epoch_sec = int(epoch_ms) / 1000  # Convert milliseconds to seconds
        return datetime.datetime.fromtimestamp(epoch_sec).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logging.error(f"Invalid Date conversion: {e}")
        return "Invalid Date"

def start_reporting():
    """Starts the Reporting.py script in the background and opens the reporting dashboard in Chrome."""
    try:
        messagebox.showinfo("Starting Reporter", "Starting Reporter. This may take a couple of seconds.")
        subprocess.Popen(["python", "Reporting.py", "-config", config_parameter], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logging.error(f"Error starting reporting: {e}")
        messagebox.ERROR("Error","Error opening reporting, please check the log file")
    port = config["port"] if "port" in config else PORT
    def open_browser():
        time.sleep(3)
        url = REPORTING_APP_URL + f":{port}"
        try:
            chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
            webbrowser.register("chrome", None, webbrowser.BackgroundBrowser(chrome_path))
            webbrowser.get("chrome").open(url)
        except webbrowser.Error:
            try:
                chrome_path = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
                webbrowser.register("chrome", None, webbrowser.BackgroundBrowser(chrome_path))
                webbrowser.get("chrome").open(url)
            except webbrowser.Error as e:
                logging.error(f"Error Opening Browser: {e}")
                messagebox.showerror("Error", "Error opening chrome. Please check the log file")

    threading.Thread(target=open_browser, daemon=True).start()

@log_function_call
def convert_date_to_epoch(date_str, date_format='%Y-%m-%d'):
    try:
        dt = datetime.datetime.strptime(date_str, date_format)
        return int(dt.timestamp() * 1000)
    except Exception as e:
        logging.error(f"Date conversion error: {e}")
        return 0

def filter_series(input_series):
    """Filters out historic rate tables and returns only the latest versions and future tables."""
    current_epoch = int(time.time()) * 1000
    latest_versions = {}
    total_series = []
    
    for item in input_series:
        item_series = item.get("series", "")
        item_version = float(item.get("version", 0))
        effective_from = item.get("effectiveFrom", "").split()[0]  # Strips the time, keeping only the date

        # Convert effective_from date to epoch
        effective_from_epoch = convert_date_to_epoch(effective_from)

        if effective_from_epoch >= current_epoch:
            total_series.append(item)
        elif item_series not in latest_versions or float(item_version) > float(latest_versions[item_series]["version"]):
            latest_versions[item_series] = item               
        
    total_series.extend(latest_versions.values())

    # Sort the list again
    total_series.sort(key=lambda x: x['series'], reverse=True)
    return total_series

def get_rate_tables(filtered=False):
    """Fetches rate tables from the API and displays them in a new window."""
    global series_window  # Use the global variable to track the rate table window

    # Close any previously opened rate table window
    if series_window is not None and series_window.winfo_exists():
        series_window.destroy()

    url = build_base_url() + "/rate-tables"
    headers = build_api_headers()
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            data = response.json()
            if not data:
                messagebox.showinfo("Info", "No Rate Tables Exist, loading an example Rate Table")
                data = EXAMPLE_RATE_TABLE

            if isinstance(data, list):
                data.sort(key=lambda x: (x.get('series', ''), float(x.get('version', 0))), reverse=True)

                # Convert epoch timestamps
                for rate_table in data:
                    if 'effectiveFrom' in rate_table and rate_table['effectiveFrom']:
                        rate_table['effectiveFrom'] = convert_epoch_to_date(rate_table['effectiveFrom'])
                    if 'created' in rate_table and rate_table['created']:
                        rate_table['created'] = convert_epoch_to_date(rate_table['created'])

                # Apply filtering if button was clicked
                if filtered:
                    data = filter_series(data)

            with open("rate_tables.json", "w") as file:
                json.dump(data, file, indent=4)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Failed to parse rate tables data.")
    else:
        messagebox.showerror("Error", f"Failed to retrieve rate tables: {response.status_code}")

    try:
        with open("rate_tables.json", "r") as file:
            data = json.load(file)
            series_window = Toplevel(root)
            series_window.title("Existing Rate Tables")
            window_width = 600  # Adjust as necessary
            window_height = 550  # Adjust as necessary
            series_window.geometry(f"{window_width}x{window_height}+{x+250}+{y+100}")
            series_window.iconbitmap(ICON)

            series_label = tk.Label(series_window, text="Select a Rate Table Series and Version:", padx=0, pady=5)
            series_label.pack()

            series_var = tk.StringVar(series_window)
            sorted_series = sorted(data, key=lambda x: (x.get('series', ''), float(x.get('version', 0))), reverse=True)

            # if selected, filter list
            if filter_var.get():
                sorted_series = filter_series(sorted_series)
            series_options = [f"{item.get('series', '')} - v{item.get('version', 'N/A')}" for item in sorted_series]

            if series_options:
                series_var.set(series_options[0])

            series_option = tk.OptionMenu(series_window, series_var, *series_options, command=lambda _: show_series())
            series_option.pack()

            series_text_area = Text(series_window, wrap="word", height=8, width=50)
            series_text_area.pack(side="top", fill="both", expand=True)

            def format_date(date_str):
                """Formats a date string to only include the date part."""
                return date_str.split()[0] if date_str else ""

            def show_series():
                """Displays the selected rate table series and version in the text area."""
                selected_series_version = series_var.get()
                selected_series, selected_version = selected_series_version.split(" - v")
                series_data = [
                    item for item in sorted_series 
                    if item.get('series', '') == selected_series and str(item.get('version', 'N/A')) == selected_version
                ]
                if series_data:
                    series_info = series_data[0]
                    series_info['effectiveFrom'] = format_date(series_info.get('effectiveFrom', ''))
                    series_info['created'] = format_date(series_info.get('created', ''))

                    # Clear the text area and configure it for bold text
                    series_text_area.config(state="normal")
                    series_text_area.delete("1.0", "end")

                    # Add bold tag
                    series_text_area.tag_configure("bold", font=("Arial", 10, "bold"))

                    # Insert formatted text with bold tags
                    series_text_area.insert("end", "Series Name:\t\t", "bold")
                    series_text_area.insert("end", f"{series_info.get('series', '')}\n")

                    series_text_area.insert("end", "Series Version:\t\t", "bold")
                    series_text_area.insert("end", f"{series_info.get('version', '')}\n\n")

                    series_text_area.insert("end", "Start Date:\t\t", "bold")
                    series_text_area.insert("end", f"{series_info.get('effectiveFrom', '')}\n")

                    series_text_area.insert("end", "Created Date:\t\t", "bold")
                    series_text_area.insert("end", f"{series_info.get('created', '')}\n\n")

                    series_text_area.insert("end", "Item Name\t\t\tVersion\t\tRate\n", "bold")
                    series_text_area.insert("end", f"{'-'*65}\n")

                    for item in series_info.get("items", []):
                        series_text_area.insert(
                            "end", 
                            f"{item.get('name', '')}\t\t\t{item.get('version', '')}\t\t{str(item.get('rate', ''))}\n"
                        )

                    series_text_area.config(state="disabled")


            def copy_to_main():
                """Copies the selected rate table series to the main text area and makes it editable."""
                text_data = series_text_area.get("1.0", "end").strip()  

                # Clean up the text data
                text_data = "\n".join(
                    line for line in text_data.splitlines() 
                    if not re.match(r"^\s*Created Date", line) and "------" not in line
                )

                # Enable and clear the main text area
                main_text_area.config(state="normal")
                main_text_area.delete("1.0", "end")

                # Configure bold tags
                main_text_area.tag_configure("bold", font=("Arial", 10, "bold"))

                # Insert formatted text with bold tags
                lines = text_data.split('\n')
                for line in lines:
                    if line.startswith("Series Name:"):
                        main_text_area.insert("end", "Series Name:\t\t", "bold")
                        main_text_area.insert("end", line.split("Series Name:")[1].strip() + "\n")
                    
                    elif line.startswith("Series Version:"):
                        main_text_area.insert("end", "Series Version:\t\t", "bold")
                        main_text_area.insert("end", line.split("Series Version:")[1].strip() + "\n")
                    
                    elif line.startswith("Start Date:"):
                        main_text_area.insert("end", "Start Date:\t\t", "bold")
                        main_text_area.insert("end", line.split("Start Date:")[1].strip() + "\n")
                    
                    elif line.startswith("Created Date:"):
                        main_text_area.insert("end", "Created Date:\t\t", "bold")
                        main_text_area.insert("end", line.split("Created Date:")[1].strip() + "\n")
                    
                    elif line.startswith("Item Name"):
                        main_text_area.insert("end", "Item Name\t\t\tVersion\t\tRate\n", "bold")
                    
                    elif "------" in line:
                        main_text_area.insert("end", f"{'-'*65}\n")
                    
                    else:
                        main_text_area.insert("end", line + "\n")

                # Keep the text area editable
                main_text_area.config(state="normal")

                result_label.config(text="Rate table successfully copied and is now editable")
                date_button.config(state=tk.NORMAL)
                post_site_button.config(state=tk.NORMAL)
                increment_version_button.config(state=tk.NORMAL)
                clear_editor_button.config(state=tk.NORMAL)

                series_window.destroy()

            def delete_rate_table():
                """Deletes the selected rate table series and version."""
                selected_series_version = series_var.get()
                selected_series, selected_version = selected_series_version.split(" - v")
                
                url = build_base_url() + f"/rate-tables/?series={selected_series}&version={selected_version}"
                headers = build_api_headers()
                
                response = requests.delete(url, headers=headers)
                if response.status_code == 204:
                    messagebox.showinfo("Success", "Rate table deleted")
                    result_label.config(text="Rate table successfully deleted")
                    series_window.destroy()
                else:
                    if response.status_code == 409:
                        messagebox.showwarning("Warning", "Rate Table is already in effect and cannot be deleted")
                        series_window.lift()  # Keep window in focus
                        series_window.focus_force()
    
        copy_button = tk.Button(series_window, text="Copy to Rate Table Editor", command=copy_to_main, width=25)
        copy_button.pack(side="left", padx=10, pady=10)

        delete_button = Button(
            series_window, 
            text="Delete Rate Table", 
            command=delete_rate_table, 
            bootstyle="danger"
            )
        delete_button.pack(side="left", padx=10, pady=10)
        
        close_button = tk.Button(series_window, text="Close", command=series_window.destroy, width=8)
        close_button.pack(side="right", padx=10, pady=10)

        show_series()
    except FileNotFoundError:
        messagebox.showerror("Error", "No rate tables found.")

def increment_version():
    """Increments the value of 'Series Version' in the main text UI."""
    text_data = main_text_area.get("1.0", "end").strip()
    
    if not text_data:
        messagebox.showerror("Error", "No data available to increment version.")
        return

    main_text_area.config(state="normal")
    main_text_area.delete("1.0", "end")

    # Add bold tag configuration
    main_text_area.tag_configure("bold", font=("Arial", 10, "bold"))

    # Split lines and handle bold text for specific fields
    for line in text_data.split("\n"):
        if line.startswith("Series Name:"):
            main_text_area.insert("end", "Series Name:\t\t", "bold")
            main_text_area.insert("end", line.split("Series Name:")[1].strip() + "\n")
        
        elif line.startswith("Series Version:"):
            main_text_area.insert("end", "Series Version:\t\t", "bold")
            version_number = int(line.split("\t")[-1]) + 1 if line.split("\t")[-1].isdigit() else 1
            main_text_area.insert("end", f"{version_number}\n")
        
        elif line.startswith("Start Date:"):
            main_text_area.insert("end", "Start Date:\t\t", "bold")
            main_text_area.insert("end", line.split("Start Date:")[1].strip() + "\n")
        
        elif line.startswith("Created Date:"):
            main_text_area.insert("end", "Created Date:\t\t", "bold")
            main_text_area.insert("end", line.split("Created Date:")[1].strip() + "\n")
        
        elif line.startswith("Item Name"):
            main_text_area.insert("end", "Item Name\t\t\tVersion\t\tRate\n", "bold")
        
        elif "------" in line:
            main_text_area.insert("end", f"{'-'*65}\n")
        
        else:
            main_text_area.insert("end", line + "\n")

    main_text_area.config(state="normal")
    result_label.config(text="Series Version incremented successfully")


def rate_table_start_date():
    """Opens a date picker dialog to select a start date for the rate table."""
    date_picker = DatePickerDialog()
    selected_date = date_picker.date_selected  # Corrected way to fetch selected date
    if selected_date:
        result_label.config(text=f"Selected Date: {selected_date}")

    text_data = main_text_area.get("1.0", "end").strip()

    if "Start Date:" in text_data:
        main_text_area.config(state="normal")
        main_text_area.delete("1.0", "end")

        # Add bold tag configuration
        main_text_area.tag_configure("bold", font=("Arial", 10, "bold"))

        for line in text_data.split("\n"):
            if line.startswith("Series Name:"):
                main_text_area.insert("end", "Series Name:\t\t", "bold")
                main_text_area.insert("end", line.split("Series Name:")[1].strip() + "\n")
            
            elif line.startswith("Series Version:"):
                main_text_area.insert("end", "Series Version:\t\t", "bold")
                main_text_area.insert("end", line.split("Series Version:")[1].strip() + "\n")
            
            elif line.startswith("Start Date:"):
                main_text_area.insert("end", "Start Date:\t\t", "bold")
                main_text_area.insert("end", f"{selected_date}\n")
            
            elif line.startswith("Created Date:"):
                main_text_area.insert("end", "Created Date:\t\t", "bold")
                main_text_area.insert("end", line.split("Created Date:")[1].strip() + "\n")
            
            elif line.startswith("Item Name"):
                main_text_area.insert("end", "Item Name\t\t\tVersion\t\tRate\n", "bold")
            
            elif "------" in line:
                main_text_area.insert("end", f"{'-'*65}\n")
            
            else:
                main_text_area.insert("end", line + "\n")

        main_text_area.config(state="normal")
        result_label.config(text="Start Date updated Successfully")


def post_to_site():
    """Posts the current contents of the Main UI to the configured site and writes it to a file."""
    text_data = main_text_area.get("1.0", "end").strip()
    if not text_data:
        messagebox.showerror("Error", "No data to post.")
        return
    
    try:
        lines = text_data.split("\n")
        rate_table = {"items": []}
        processing_items = False  # Flag to track when to process item lines

        for line in lines:
            line = line.strip()

            # Identify metadata before processing items
            if line.startswith("Series Name:"):
                rate_table["series"] = line.split("\t")[-1].strip()
            elif line.startswith("Series Version:"):
                rate_table["version"] = line.split("\t")[-1].strip()
            elif line.startswith("Start Date:"):
                rate_table["effectiveFrom"] = convert_date_to_epoch(line.split("\t")[-1].strip())
            elif line.startswith("Item Name"):
                processing_items = True  # Begin processing items after this line
                continue  # Skip the header line itself
            
            # Process items after "Item Name"
            if processing_items and line and "\t" in line:
                parts = re.split(r'\t+', line)  # Handle multiple tab spaces
                if len(parts) >= 3:
                    rate_table["items"].append({
                        "name": parts[0].strip(),
                        "version": parts[1].strip(),
                        "rate": float(parts[2].strip())
                    })
        ############################################################
        # Write to JSON file  Enable for debug only
        ############################################################
        #with open("rate_table_start_date_table.json", "w") as json_file:
        #    json.dump(rate_table, json_file, indent=4)

        # Determine API endpoint
        api_url = build_base_url() + "/rate-tables"
        headers = build_api_headers()
        response = requests.post(api_url, headers=headers, json=rate_table)

        if response.status_code in [200, 201]:
            messagebox.showinfo("Success", "Rate Table posted successfully")
        else:
            if response.status_code == 409:
                messagebox.showwarning("Warning", "Rate Table with the specified Series and Version already exists")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to process data: {str(e)}")

def clear_editor():
    """Clears the contents of the Main UI."""
    main_text_area.config(state="normal")
    main_text_area.delete("1.0", "end")
    main_text_area.config(state="normal")
    increment_version_button.config(state=tk.DISABLED)
    date_button.config(state=tk.DISABLED)
    post_site_button.config(state=tk.DISABLED)
    clear_editor_button.config(state=tk.DISABLED)
    result_label.config(text="Editor cleared successfully")

def open_user_guide():
    """Opens the Dynamic Monetization User Guide in the default web browser."""
    webbrowser.open("https://docs.revenera.com/dm/dynamicmonetization_ug/Content/helplibrary/DMGettingStarted.htm")

def open_api_ref():
    """Opens the Rate Table API Reference in the default web browser."""
    webbrowser.open("https://fnoapi-dynamicmonetization.redoc.ly/#operation/getRateTables")

def register_customer():
    """Registers a new customer using DAPI."""
    customer_id = customer_id_entry.get().strip()
    customer_name = customer_name_entry.get().strip()
    
    # Validate inputs
    if not customer_id or not customer_name:
        messagebox.showerror("Error", "Customer ID and Customer Name are required.")
        return

    # Determine API URL
    url = build_base_url() + "/instances"
    headers = build_api_headers()


    payload = {
        "shortName": customer_name,
        "accountId": customer_id
    }

    try:
        # Check to see if the customer already exists
        query_params = {
            "accountId": customer_id,
            "default": True
        }

        check_exists_response = requests.get(url=url,headers=headers,params=query_params)
        if check_exists_response.status_code in [200, 201]:
            exists_data = check_exists_response.json().get("content")
            if len(exists_data) > 0:
                customer_instance_id = exists_data[0].get("id")

                # Ask if you want to continue
                confirm_continue = messagebox.askyesno("Customer Exists: ", f"Customer Account ID: {customer_id} Already Exists. Would you like to entitle additional tokens?")
                if confirm_continue:
                    return customer_instance_id
                else:
                    return 0 #Zero means customer exists


        response = requests.post(url, headers=headers, json=payload)

        if response.status_code in [200, 201]:
            response_data = response.json()
            elastic_instance_id = response_data.get("id", "Unknown")

            messagebox.showinfo("Success", f"Customer registered successfully!\nElastic Instance ID: {elastic_instance_id}")
            return elastic_instance_id

        else:
            messagebox.showerror("Error", f"Failed to register customer: {response.status_code}\n{response.text}")

    except Exception as e:
        messagebox.showerror("Error", f"Request failed: {str(e)}")

def get_rate_tables_names():
    """Fetches the names of rate tables from the API."""
    url = build_base_url() + "/rate-tables"
    headers = build_api_headers()
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            data = response.json()
            table_list = []
            for entry in data:
                if entry["series"] not in table_list:
                    table_list.append(entry["series"])
            return table_list
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Failed to parse rate tables data.")
    else:
        messagebox.showerror("Error", f"Failed to retrieve rate tables: {response.status_code}")

def generate_uuid():
    """Generates a new UUID."""
    return str(uuid.uuid4())

# After Registering, map the token line items
def map_token_line_item(instance_id):
    """Maps token line items to a customer instance."""
    customer_id = customer_id_entry.get().strip()
    token_number = token_number_entry.get().strip()
    start_date = start_date_label.cget("text")
    end_date = end_date_label.cget("text")
    selected_rate_table = rate_table_var.get()
    start_epoch = convert_date_to_epoch(start_date)
    
    if end_date == "Permanent":
        end_epoch = PERMANENT_EPOCH
    else:
        end_epoch = convert_date_to_epoch(end_date)
    
    # Call API
    url = build_base_url() + f"/instances/{instance_id}/line-items"
    headers = build_api_headers()

    line_item_payload = {
        "activationId": generate_uuid(),
        "state": "DEPLOYED",
        "quantity": int(token_number),
        "start": start_epoch,
        "end": end_epoch,
        "used": 0,
        "attributes": {
            "elastic": True,
            "rateTableSeries": selected_rate_table
        }
    }
    json_payload = json.dumps(line_item_payload)

    try:
        response = requests.put(url, headers=headers, data=json_payload)

        if response.status_code in [200, 201]:         
            messagebox.showinfo("Success: ", f"{token_number} Tokens successfully entitled to: {customer_id}")

        else:
            messagebox.showerror("Error", f"Failed to Entitle tokens to customer: {response.status_code}\n{response.text}")

    except Exception as e:
        messagebox.showerror("Error", f"Request failed: {str(e)}")   

# Register Customer Function
def create_and_map_customer():
    """Creates and maps a new customer."""
    customer_id = customer_id_entry.get().strip()
    token_number = token_number_entry.get().strip()
    start_date = start_date_label.cget("text")
    end_date = end_date_label.cget("text")
    selected_rate_table = rate_table_var.get()
    isPermanent = permanent_var.get()
    if not customer_id or not token_number or not start_date or not end_date or not selected_rate_table or end_date =="Select End Date" or start_date == "Select Start Date":
        messagebox.showerror("Error","All fields are required.")
        return
    elif not isPermanent and start_date >= end_date:
        messagebox.showerror("Error","End Date must be after Start Date.")
        return
    else:
        elastic_instance_id = register_customer()
        if (elastic_instance_id != 0): #if it's 0 that means customer exists
            map_token_line_item(elastic_instance_id)
        customer_id_entry.delete(0, tk.END)
        customer_name_entry.delete(0, tk.END)
        token_number_entry.delete(0, tk.END)
        start_date_label.config(text=get_default_date())
        end_date_label.config(text="Select End Date")
        permanent_var.set(0) # Reset checkbox            

def tab_selected_changed(event):
    """Update customer dropdown values when the 'Manage Existing Customers' tab is selected."""
    global customer_data
    if notebook.select() == notebook.tabs()[0]:
        result_label.config(text="")

    elif notebook.select() == notebook.tabs()[1]:
        # **Refresh Rate Tables on New Customer Registration Tab**
        new_rate_table_list = get_rate_tables_names()

        if new_rate_table_list:
            rate_table_dropdown["values"] = new_rate_table_list  # Update dropdown values
            rate_table_var.set(new_rate_table_list[0])  # Set first value as default
        else:
            rate_table_dropdown["values"] = []  # Clear dropdown if no data
            rate_table_var.set("")  # Reset selection

    elif notebook.select() == notebook.tabs()[2]:  # Only update on the third tab
        customer_data = load_customer_names()  # Reload customer list
        
        # Update dropdown values
        customer_dropdown["values"] = [c["accountId"] for c in customer_data]
        
        # Set the first customer by default if available
        if customer_data:
            selected_account_var.set(customer_data[0]["accountId"])
            get_customer_line_items()
        else:
            selected_account_var.set("")  # Clear selection if no customers exist

def on_env_change():
    """Reload customer names and refresh rate table dropdown when the environment selection changes."""
    
    if notebook.select() == notebook.tabs()[0]: # Only update on the first tab
        if clear_editor_button.instate(('!disabled',)):  #If button not disabled
            confirm_clear_editor = messagebox.askyesno("Clear Editor?", "Do you want to clear the editor as you change environment?")
            if confirm_clear_editor:
                clear_editor()
        return
    
    elif notebook.select() == notebook.tabs()[1] or notebook.select() == notebook.tabs()[2]: 
        global customer_data
        customer_data = load_customer_names()  # Reload customer list

        # Update the customer dropdown and their line items
        customer_dropdown["values"] = [c["accountId"] for c in customer_data]
        if customer_data:
            selected_account_var.set(customer_data[0]["accountId"])  # Set first option
        else:
            selected_account_var.set("")  # Clear selection if no data
        get_customer_line_items()  # Refresh line items
        
        if notebook.select() == notebook.tabs()[1]:  #If on the New Customers Tab
            # **Refresh Rate Tables on New Customer Registration Tab**
            new_rate_table_list = get_rate_tables_names()

            if new_rate_table_list:
                rate_table_dropdown["values"] = new_rate_table_list  # Update dropdown values
                rate_table_var.set(new_rate_table_list[0])  # Set first value as default
            else:
                rate_table_dropdown["values"] = []  # Clear dropdown if no data
                rate_table_var.set("")  # Reset selection

def load_customer_names():
    """Loads customer names from the API, filtering out excluded account IDs."""
    customer_data = []
    env_option = env_var.get()
    excluded_prefixes = config.get("accountid_exclude_uat" if env_option == UAT_OPTION else "accountid_exclude_prod", [])
    excluded_prefixes = [prefix.lower() for prefix in excluded_prefixes]  # Ensure case-insensitive matching

    url = build_base_url() + "/instances/?size=500"
    headers = build_api_headers()

    try:
        response = requests.get(url, headers=headers)
        if response.status_code in [200, 201]:
            response_data = response.json()
            instances = response_data.get("content", [])
            
            for entry in instances:
                account_id = entry.get("accountId", "").lower()
                if any(account_id.startswith(prefix) for prefix in excluded_prefixes):
                    continue  # Skip excluded accounts
                
                customer_data.append({
                    "accountId": entry["accountId"],
                    "shortName": entry["shortName"],
                    "id": entry["id"]
                })
            
            #customer_data.sort(key=lambda x: x["accountId"], reverse=(env_option == UAT_OPTION))  # Sort descending for UAT
            customer_data.sort(key=lambda x: x["accountId"].lower())
        else:
            messagebox.showerror("Error", f"Failed to get customer list: {response.status_code}\n{response.text}")
    except Exception as e:
        messagebox.showerror("Error", f"Request failed: {str(e)}")
    
    return customer_data

def get_customer_line_items():
    """Fetches and displays line items for the selected customer in a Treeview widget."""
    selected_account_id = selected_account_var.get()
    selected_customer = next((c for c in customer_data if c["accountId"] == selected_account_id), None)
    
    if not selected_customer :
        # Clear previous content
        for row in line_items_table.get_children():
            line_items_table.delete(row)
        return
    
    customer_id = selected_customer["id"]
    edit_customer_id.set(customer_id)  # Set the customer ID for editing
    
    url = build_base_url() + f"/instances/{customer_id}/line-items"
    headers = build_api_headers()

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()

        # Clear previous content
        for row in line_items_table.get_children():
            line_items_table.delete(row)

        if not data:
            messagebox.showinfo("Info", "No line items found for this customer.")
            return

        # Convert and sort data by Start Date
        formatted_data = []
        for item in data:
            start_epoch = item.get("start", 0)
            start_date = convert_epoch_to_date(start_epoch)[:10]  # Extract YYYY-MM-DD
            end_epoch = item.get("end", "")
            end_date = "Permanent" if end_epoch == PERMANENT_EPOCH else convert_epoch_to_date(end_epoch)[:10]  # Extract YYYY-MM-DD
            quantity = item.get("quantity", "N/A")
            used = round(float(item.get("used", 0)), 1)  # Round Used to 1 decimal place
            percent_used = round((used / quantity) * 100, 1) if quantity and quantity != "N/A" and quantity > 0 else 0.0
            rate_table_series = item.get("attributes", {}).get("rateTableSeries", "N/A")
            state = item.get("state", "N/A")  # Add state field

            formatted_data.append((start_date, end_date, quantity, used, percent_used, rate_table_series, state, json.dumps(item)))

        # Sort by Start Date
        formatted_data.sort()

        # Populate the Treeview
        for row in formatted_data:
            line_items_table.insert("", "end", values=row)
        
        # Display Elastic Instance ID 
        customer_id_label.config(text=f"Instance ID: {customer_id}", padding=0)
    else:
        messagebox.showerror("Error", f"Failed to get line items: {response.status_code}")

def edit_line_item():
    """Opens a window to edit the selected line item."""
    selected_item = line_items_table.selection()
    # Check to see if an item is selected
    if not selected_item:
        messagebox.showerror("Error", "Please select a line item to edit.")
        return
    item_values = line_items_table.item(selected_item, "values")
    item_string = item_values[7]
    original_item = json.loads(item_string)

    edit_window = tk.Toplevel(root)
    edit_window.title("Edit Line Item")
    window_width = 630  # Adjust as necessary
    window_height = 600  # Adjust as necessary
    edit_window.geometry(f"{window_width}x{window_height}+{x+250}+{y+100}")
    edit_window.iconbitmap(ICON)

    edit_title_frame = tk.Frame(edit_window)
    edit_title_frame.grid(row=0, column=0, sticky="w", pady=30, padx=20)
    ttk.Label(edit_title_frame, text="Edit Line Item", font=("Arial", 12, "bold")).grid(row=0, column=0)

    # Rate Table Dropdown
    edit_rate_frame = tk.Frame(edit_window)
    edit_rate_frame.grid(row=1, column=0, sticky="w", pady=20, padx=20)
    tk.Label(edit_rate_frame, text="Rate Table:", font=FONT).grid(row=1, column=0)
    edit_rate_table_var = tk.StringVar(edit_rate_frame)
    edit_rate_table_names = get_rate_tables_names()
    selected_table = item_values[5] if item_values[5] in edit_rate_table_names else ""
    edit_rate_table_var.set(selected_table)
    edit_rate_table_dropdown = ttk.Combobox(edit_rate_frame, textvariable=edit_rate_table_var, values=edit_rate_table_names, width=15)
    edit_rate_table_dropdown.state(['readonly'])
    edit_rate_table_dropdown.grid(row=1, column=1, padx=20)

    # Token Quantity Entry
    edit_quantity_frame = tk.Frame(edit_window)
    edit_quantity_frame.grid(row=2, column=0, sticky="w", pady=20, padx=20)
    tk.Label(edit_quantity_frame, text="Quantity:", font=FONT).grid(row=2, column=0)
    edit_quantity_entry = tk.Entry(edit_quantity_frame, font=FONT,validate="key", validatecommand=vcmd, width=16)
    edit_quantity_entry.insert(0, item_values[2])
    edit_quantity_entry.grid(row=2, column=1, padx=37)

    # Start Date
    old_start_date = item_values[0]
    edit_start_date_frame = tk.Frame(edit_window)
    edit_start_date_frame.grid(row=3, column=0,sticky="w", pady=20, padx=20)
    tk.Label(edit_start_date_frame,text="Start Date:", font=("Arial", 10, "normal")).grid(row=3, column=0)
    edit_start_date_label = ttk.Label(edit_start_date_frame,text=item_values[0], font=FONT, width=15)
    edit_start_date_label.grid(row=3, column=1, padx=22)
    edit_start_date_btn = ttk.Button(edit_start_date_frame, text="Pick Date", command=lambda: open_calendar(edit_start_date_label,edit_start_date_label))
    edit_start_date_btn.grid(row=3, column=2, padx=10)


    # End Date
    old_end_date = item_values[1]
    edit_end_date_frame = tk.Frame(edit_window)
    edit_end_date_frame.grid(row=4, column=0,sticky="w", pady=20, padx=20)
    ttk.Label(edit_end_date_frame, text="End Date:", font=("Arial", 10, "normal")).grid(row=4, column=0)
    edit_end_date_label = ttk.Label(edit_end_date_frame, text=item_values[1], font=FONT, width=15)
    edit_end_date_label.grid(row=4, column=1, padx=30)
    edit_end_date_btn = ttk.Button(edit_end_date_frame, text="Pick Date", command=lambda: open_calendar(edit_end_date_label,edit_end_date_label))
    edit_end_date_btn.grid(row=4, column=2, padx=0)

    # Function to toggle the date fields based on checkbox state
    def toggle_permanent_edit(previous_date=None):
        if edit_permanent_var.get():
            edit_end_date_btn.config(state=tk.DISABLED)
            edit_end_date_label.config(text="Permanent")
        else:
            edit_end_date_btn.config(state=tk.NORMAL)
            if previous_date and previous_date != "Permanent":
                edit_end_date_label.config(text=previous_date)
            else:
                edit_end_date_label.config(text="Select End Date")

    # Permanent Checkbox
    edit_permanent_var = tk.BooleanVar(edit_end_date_frame)
    previous_end_date = item_values[1]
    if previous_end_date == "Permanent":
        edit_permanent_var.set(True)
        edit_end_date_btn.config(state=tk.DISABLED)
    edit_permanent_checkbox = ttk.Checkbutton(edit_end_date_frame, text="Permanent", variable=edit_permanent_var, command=lambda: toggle_permanent_edit(old_end_date))
    edit_permanent_checkbox.grid(row=4, column=3, padx=10)

    # State Dropdown
    edit_state_frame = tk.Frame(edit_window)
    edit_state_frame.grid(row=5, column=0, sticky="w", pady=20, padx=20)
    tk.Label(edit_state_frame, text="State:", font=FONT).grid(row=5, column=0)
    edit_state_var = tk.StringVar(edit_state_frame)
    state_options = ["DEPLOYED", "INACTIVE", "OBSOLETE"]
    edit_state_var.set(original_item.get("state", "DEPLOYED"))
    edit_state_dropdown = ttk.Combobox(edit_state_frame, textvariable=edit_state_var, values=state_options, width=15)
    edit_state_dropdown.state(['readonly'])
    edit_state_dropdown.grid(row=5, column=1, padx=60)

    def apply_changes():
        new_quantity = int(edit_quantity_entry.get())
        original_item['quantity']= new_quantity if float(new_quantity) > original_item['used'] else messagebox.ERROR('Error',"You cannot reduce the token amount to a quanity less than the amount of tokens used.")# quantity can't be less than amount used.
        original_item['start'] = convert_date_to_epoch(edit_start_date_label.cget("text"))
        original_item['end'] = PERMANENT_EPOCH if edit_permanent_var.get() else convert_date_to_epoch(edit_end_date_label.cget("text"))
        original_item['attributes']['rateTableSeries'] = edit_rate_table_var.get()
        original_item['state'] = edit_state_var.get()

        # Check if the state is changed to OBSOLETE
        if original_item['state'] == 'OBSOLETE':
            confirm_obsolete = messagebox.askyesno("Warning", "Are you sure you want to OBSOLETE this line item? This is a permanent action and cannot be undone.")
            if not confirm_obsolete:
                return

        customer_instance_id = edit_customer_id.get()

        # Call API:
        url = build_base_url() + f"/instances/{customer_instance_id}/line-items"
        headers = build_api_headers()

        # Prepare JSON payload of the updated item
        json_payload = json.dumps(original_item)

        try:
            response = requests.put(url, headers=headers, data=json_payload)

            if response.status_code in [200, 201]:         
                messagebox.showinfo("Success: ", f"Successfully Updated Line Item")

            else:
                messagebox.showerror("Error", f"Failed to Update Line Item: {response.status_code}\n{response.text}")

        except Exception as e:
            messagebox.showerror("Error", f"Request failed: {str(e)}")   

        edit_window.destroy()
        get_customer_line_items()

    # Apply or cancel buttons
    edit_button_frame = tk.Frame(edit_window)
    edit_button_frame.grid(row=6, column=0,sticky="w", pady=60, padx=20)
    edit_apply_btn = ttk.Button(edit_button_frame, text="Apply Changes", command=apply_changes, width=14)
    edit_apply_btn.grid(row=6, column=0)
    edit_cancel_btn = ttk.Button(edit_button_frame, text="Cancel", command=edit_window.destroy, width=14)
    edit_cancel_btn.grid(row=6, column=5, padx=260)

def delete_line_item():
    """Deletes the selected line item."""
    selected_item = line_items_table.selection()
    if not selected_item:
        messagebox.showerror("Error", "Please select a line item to delete.")
        return

    item_values = line_items_table.item(selected_item, "values")
    item_string = item_values[7]
    original_item = json.loads(item_string)
    activation_id = original_item.get("activationId", "")
    customer_instance_id = edit_customer_id.get()

    # Check if the line item state is OBSOLETE
    if original_item.get("state") != "OBSOLETE":
        messagebox.showwarning("Warning", "Line Items can only be deleted in an OBSOLETE state.")
        return

    # Confirm deletion
    confirm_delete = messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete this line item?")
    if not confirm_delete:
        return

    url = build_base_url() + f"/instances/{customer_instance_id}/line-items/{activation_id}"
    headers = build_api_headers()

    try:
        response = requests.delete(url, headers=headers)
        if response.status_code == 204:
            messagebox.showinfo("Success", "Successfully Deleted Line Item")
            get_customer_line_items()  # Refresh the line items window
        else:
            messagebox.showerror("Error", f"Failed to Delete Line Item: {response.status_code}\n{response.text}")
    except Exception as e:
        messagebox.showerror("Error", f"Request failed: {str(e)}")

    return

def open_calendar(label,calendar_start_date=None):
    """ Opens a date picker and updates the given label with the selected date. """
    if calendar_start_date is not None:
        try:
            date = datetime.datetime.strptime(calendar_start_date.cget("text"), "%Y-%m-%d")
            date_picker = DatePickerDialog(startdate=date)
        except:
            date_picker = DatePickerDialog()
    else:
        date_picker = DatePickerDialog() 
    selected_date = date_picker.date_selected
    label.config(text=selected_date)

def validate_token_input(P):
    return P.isdigit() and int(P) > 0 if P else True

# Enable buttons when a row is selected
def on_table_select(event):
    selected = line_items_table.selection()
    if selected:
        edit_button.config(state=tk.NORMAL)
        delete_button.config(state=tk.NORMAL)
        email_button.config(state=tk.NORMAL)
    else:
        edit_button.config(state=tk.DISABLED)
        delete_button.config(state=tk.DISABLED)
        email_button.config(state=tk.DISABLED)

# Function to toggle the date fields based on checkbox state
def toggle_permanent():
    if permanent_var.get():
        end_date_btn.config(state=tk.DISABLED)
        end_date_label.config(text="Permanent")
    else:
        end_date_btn.config(state=tk.NORMAL)
        end_date_label.config(text="Select End Date")

def get_default_date():
    today = datetime.datetime.today()
    today = datetime.datetime.now()
    year = today.year
    month = today.strftime("%m")
    day = today.strftime("%d")
    return f"{year}-{month}-{day}"

def send_email(to_address, subject, body):
    """Send an email with the specified subject and body to the given address."""
    config = read_config()
    try:
        from_address = config['from_email']
        password = config['email_pwd']
        smtp_server = config['smtp_server']  # Ensure this is the correct SMTP server address
    except KeyError as e:
        messagebox.showerror("Configuration Error", f"Missing configuration key: {str(e)}")
        return

    smtp_port = 587  # Ensure this is the correct SMTP port

    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = to_address
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        # Verify SMTP server address
        socket.gethostbyname(smtp_server)
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(from_address, password)
        text = msg.as_string()
        server.sendmail(from_address, to_address, text)
        server.quit()
        messagebox.showinfo("Success", "Email sent successfully")
    except smtplib.SMTPAuthenticationError:
        messagebox.showerror("Authentication Error", "Failed to authenticate with the SMTP server. Please check your username and password.")
    except smtplib.SMTPConnectError:
        messagebox.showerror("Connection Error", "Failed to connect to the SMTP server. Please check the server address and port.")
    except smtplib.SMTPException as e:
        messagebox.showerror("SMTP Error", f"An SMTP error occurred: {str(e)}")
    except socket.gaierror as e:
        messagebox.showerror("Address Error", f"Address-related error connecting to server: {str(e)}. Please check the SMTP server address.")
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")

def email_line_item():
    """Prompt the user to enter an email address and send the selected line item."""
    selected_item = line_items_table.selection()
    if not selected_item:
        messagebox.showerror("Error", "Please select a line item to email.")
        return

    item_values = line_items_table.item(selected_item, "values")
    item_string = item_values[7]
    original_item = json.loads(item_string)

    email_window = Toplevel(root)
    email_window.title("Email Line Item Details")
    email_window.geometry("450x150+700+450")
    email_window.iconbitmap(ICON)

    tk.Label(email_window, text="Enter Customer Email Address:").pack(pady=5)
    email_entry = tk.Entry(email_window, width=40)
    email_entry.pack(pady=5)

    def send():
        to_address = email_entry.get()
        if not to_address:
            messagebox.showerror("Error", "Email address is required.")
            return

        subject = "Token Order Details"
        body = (
            f"Elastic Instance ID:\t{edit_customer_id.get()}\n\n"
            f"Token Quantity:\t\t{original_item.get('quantity', 'N/A')}\n"
            f"Quantity Used:\t\t{float(original_item.get('used', 0)):.2f}\n\n"
            f"Start Date:\t\t{convert_epoch_to_date(original_item.get('start', 0)).split()[0]}\n"
            f"End Date:\t\t{'Permanent' if original_item.get('end', 0) == PERMANENT_EPOCH else convert_epoch_to_date(original_item.get('end', 0)).split()[0]}\n"
        )

        send_email(to_address, subject, body)
        email_window.destroy()

    tk.Button(email_window, text="Send Email", command=send, width=12).pack(side="left", padx=10, pady=10)
    tk.Button(email_window, text="Close", command=email_window.destroy, width=8).pack(side="right", padx=10, pady=10)

############################################################################################################
# Main Window Development
############################################################################################################
config = read_config()

# Create the main application window
root = ttkb.Window(themename=config["theme"])
root.title("FlexNet EAST (Elastic Access Standalone Tool)")

# Set window size and position
window_width, window_height = config['main_window_width'], config['main_window_height']
screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
x, y = (screen_width - window_width) // 2, (screen_height - window_height) // 2
root.geometry(f"{window_width}x{window_height}+{x}+{y-40}")
root.iconbitmap(ICON)  


# Create a Notebook (Tabbed Interface)
notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill="both")

# Create "Rate Table Generator" tab
rate_table_tab = ttk.Frame(notebook)
notebook.add(rate_table_tab, text="Rate Table Editor", padding= 5)

# Create "Customer Entitlements" tab
customer_entitlements_tab = ttk.Frame(notebook)
notebook.add(customer_entitlements_tab, text="Entitle New & Existing Customers", padding= 5)

# Create "Manage Existing Customers" tab
existing_customer_tab = ttk.Frame(notebook)
notebook.add(existing_customer_tab, text="Manage Customer Entitlements", padding=5)

# UI Components for "Rate Table Generator" tab
env_var = tk.StringVar(value=UAT_OPTION)


############################################################################################################
# Manage Rate Table Tab
############################################################################################################

# Radio Buttons for Environment Selection
radio_frame = tk.Frame(rate_table_tab)
radio_frame.pack(side="top", anchor="nw", pady=30)
tk.Radiobutton(radio_frame, text="Production", variable=env_var, value="Production", command=on_env_change).pack(side="left", padx=10)
tk.Radiobutton(radio_frame, text="UAT", variable=env_var, value=UAT_OPTION, command=on_env_change).pack(side="left", padx=10)

# Tenant label
ttk.Label(rate_table_tab, text=f"Tenant: {config['site']}", font=("Arial", 10, "bold")).place(x=30, y=8)

# Buttons for Rate Table Actions
button_width = 23

# Add a new button to get filtered rate tables
filter_var = tk.BooleanVar()
ttk.Button(rate_table_tab, text="Get Current/Future Tables", command=lambda:get_rate_tables(filtered=True), padding=(5, 7), width=button_width).place(x=10, y=120)
ttk.Button(rate_table_tab, text="Get All Rate Tables", command=get_rate_tables, padding=(5, 7), width=button_width).place(x=10, y=170)
increment_version_button = ttk.Button(rate_table_tab, text="Increment Series Version", command=increment_version, padding=(5, 7), width=button_width, state=tk.DISABLED)
increment_version_button.place(x=10, y=220)
date_button = ttk.Button(rate_table_tab, text="Select New Start Date", command=rate_table_start_date, padding=(5, 7), width=button_width, state=tk.DISABLED)
date_button.place(x=10, y=270)
post_site_button = ttk.Button(rate_table_tab, text="Post New Rate Table", command=post_to_site, padding=(5, 7), width=button_width, state=tk.DISABLED)
post_site_button.place(x=10, y=320)

clear_editor_button = ttk.Button(rate_table_tab, text="Clear Editor", command=clear_editor, padding=(5, 7), width=button_width, state=tk.DISABLED)
clear_editor_button.place(x=config['clear_edit_button_x'], y=120)



# Text Area for Rate Table
main_text_area = Text(rate_table_tab, wrap="word", height=20, width=config['rate_table_editor_width'])
main_text_area.pack(padx=config['rate_table_editor_padding'])

# Result Label
result_label = tk.Label(rate_table_tab, text="", font=("Arial", 10, "bold"))
result_label.pack(pady=10)

# Create a frame for bottom buttons
bottom_frame_rate_table_tab = ttk.Frame(rate_table_tab)
bottom_frame_rate_table_tab.pack(side="bottom", fill="x", pady=10)  # Anchors to bottom with padding
bottom_frame_customer_entitlements_tab = ttk.Frame(customer_entitlements_tab)
bottom_frame_customer_entitlements_tab.pack(side="bottom", fill="x", pady=10)  # Anchors to bottom with padding
bottom_frame_existing_customer_tab = ttk.Frame(existing_customer_tab)
bottom_frame_existing_customer_tab.pack(side="bottom", fill="x", pady=10)  # Anchors to bottom with padding

# User Guide and API Reference Buttons
dmug_button = Button(
            bottom_frame_rate_table_tab, 
            text="Dynamic Monetization User Guide", 
            command=open_user_guide,
            bootstyle="success",
            padding=(5,7),
            width=30
            )
dmug_button.pack(side="left", padx=10, pady=10)
apiref_button = Button(
            bottom_frame_rate_table_tab, 
            text="Rate Table API Reference", 
            command=open_api_ref,
            bootstyle="success",
            padding=(5,7),
            width=30
            )
apiref_button.pack(side="left", padx=10, pady=10)


#ttk.Button(bottom_frame_rate_table_tab, text="Dynamic Monetization User Guide", command=open_user_guide, padding=(5, 7), width=30).pack(side="left", padx=10, pady=5)
#ttk.Button(bottom_frame_rate_table_tab, text="Rate Table API Reference", command=open_api_ref, padding=(5, 7), width=30).pack(side="left", padx=10, pady=5)
# Create a new button in bottom_frame_existing_customer_tab


# Place the "Exit" button on the bottom right
exit_button1 = ttk.Button(bottom_frame_rate_table_tab, text="Exit", command=root.quit, padding=(20, 5))
exit_button1.pack(side="right", padx=10, pady=5)  # Aligns it to the bottom-right
exit_button2 = ttk.Button(bottom_frame_customer_entitlements_tab, text="Exit", command=root.quit, padding=(20, 5))
exit_button2.pack(side="right", padx=10, pady=5)  # Aligns it to the bottom-right
exit_button3 = ttk.Button(bottom_frame_existing_customer_tab, text="Exit", command=root.quit, padding=(20, 5))
exit_button3.pack(side="right", padx=10, pady=5)  # Aligns it to the bottom-right


############################################################################################################
# New Customer Registation Tab
############################################################################################################

def on_customer_id_change(*args):
    """Automatically copy the entered Customer ID to the Customer Name field."""
    customer_name_entry.delete(0, tk.END)
    customer_name_entry.insert(0, customer_id_entry.get())

# Tenant label (Upper Left at x=30, y=10)
ttk.Label(customer_entitlements_tab, text=f"Tenant: {config['site']}", font=("Arial", 10, "bold")).place(x=30, y=8)

# Radio Buttons for Environment Selection (Moved to x=30, y=40, Left Side)
radio_frame = tk.Frame(customer_entitlements_tab)
radio_frame.pack(side="top", anchor="nw", pady=30)

tk.Radiobutton(radio_frame, text="Production", variable=env_var, value="Production", command=on_env_change).pack(side="left", padx=10)
tk.Radiobutton(radio_frame, text="UAT", variable=env_var, value=UAT_OPTION, command=on_env_change).pack(side="left", padx=10)

# Create a frame for better layout management
customer_frame = tk.Frame(customer_entitlements_tab)
customer_frame.place(x=30, y=150)  # Position below the environment selection

# Customer ID Label and Entry (Left side)
ttk.Label(customer_frame, text="Customer ID:", font=("Arial", 10, "normal")).pack(side="left", padx=5)
customer_id_entry = ttk.Entry(customer_frame, width=25)
customer_id_entry.pack(side="left", padx=5)
customer_id_entry.bind("<KeyRelease>", on_customer_id_change)

# Customer Name Label and Entry (Right of Customer ID)
ttk.Label(customer_frame, text="Customer Name:", font=("Arial", 10, "normal")).pack(side="left", padx=20)
customer_name_entry = ttk.Entry(customer_frame, width=24)
customer_name_entry.pack(side="left", padx=6)

# Create extra frame for better layout management
entry_frame = tk.Frame(customer_entitlements_tab)
entry_frame.place(x=30, y=220) 

ttk.Label(entry_frame, text="Rate Table:", font=("Arial", 10, "normal")).pack(side="left", padx=5)
rate_table_var = tk.StringVar()

rate_table_list = []
rate_table_dropdown = ttk.Combobox(entry_frame, textvariable=rate_table_var, values=rate_table_list, width=23)
rate_table_dropdown.state(['readonly'])
rate_table_dropdown.pack(side="left", padx=20)
ttk.Label(entry_frame, text="Number of Tokens:", font=("Arial", 10, "normal")).pack(side="left", padx=5)

vcmd = (entry_frame.register(validate_token_input), "%P")

token_number_entry = ttk.Entry(entry_frame, width=22, font=("Arial", 10, "normal"), validate="key", validatecommand=vcmd)
token_number_entry.pack(side="left", padx=3)

start_date_frame = tk.Frame(customer_entitlements_tab)
start_date_frame.place(x=30, y=300) 

ttk.Label(start_date_frame, text="Start Date:", font=("Arial", 10, "normal")).pack(side="left", padx=5)

start_date_label = ttk.Label(start_date_frame, text=get_default_date(), font=("Arial", 10, "normal"), width=15)
start_date_label.pack(side="left", padx=23)

start_date_btn = ttk.Button(start_date_frame, text="Pick Date", command=lambda: open_calendar(start_date_label), width=10)
start_date_btn.pack(side="left", padx=5)

end_date_frame = tk.Frame(customer_entitlements_tab)
end_date_frame.place(x=30, y=380) 

ttk.Label(end_date_frame, text="End Date:", font=("Arial", 10, "normal")).pack(side="left", padx=5)

end_date_label = ttk.Label(end_date_frame, text="Select End Date", font=("Arial", 10, "normal"), width=15)
end_date_label.pack(side="left", padx=28)

end_date_btn = ttk.Button(end_date_frame, text="Pick Date", command=lambda: open_calendar(end_date_label), width=10)
end_date_btn.pack(side="left")

permanent_var = tk.BooleanVar()
permanent_checkbox = ttk.Checkbutton(end_date_frame, text="Permanent", variable=permanent_var, command=toggle_permanent)
permanent_checkbox.pack(side="left", padx=40)

create_frame = tk.Frame(customer_entitlements_tab)
create_frame.place(x=30, y=470)

generate_button = ttk.Button(create_frame, text="Create & Entitle Customer", command=create_and_map_customer, padding=(5, 7), width=28)
generate_button.pack(padx=10, pady=70)

map_label = ttk.Label(create_frame, text="", wraplength=400)
map_label.pack()


############################################################################################################
# Existing Customer Entitlements Tab
############################################################################################################

# Tenant label (Upper Left at x=30, y=10)
ttk.Label(existing_customer_tab, text=f"Tenant: {config['site']}", font=("Arial", 10, "bold")).place(x=30, y=8)

# Radio Buttons for Environment Selection (Updated)
radio_frame = tk.Frame(existing_customer_tab)
radio_frame.pack(side="top", anchor="nw", pady=30)

tk.Radiobutton(radio_frame, text="Production", variable=env_var, value="Production", command=on_env_change).pack(side="left", padx=10)
tk.Radiobutton(radio_frame, text="UAT", variable=env_var, value=UAT_OPTION, command=on_env_change).pack(side="left", padx=10)

# UI Components for "Manage Existing Customer" tab

# Bind the function to tab selection
notebook.bind("<<NotebookTabChanged>>", tab_selected_changed)

# Load customers and update UI
ttk.Label(existing_customer_tab, text="Select Customer (Account ID):", font=FONT).pack()
customer_data = load_customer_names()
selected_account_var = tk.StringVar(existing_customer_tab)

if customer_data:
    selected_account_var.set(customer_data[0]["accountId"])
customer_dropdown = ttk.Combobox(existing_customer_tab, textvariable=selected_account_var,
                                 values=[c["accountId"] for c in customer_data], width=40, state='readonly', height=70)
customer_dropdown.bind("<<ComboboxSelected>>", lambda event: get_customer_line_items())
customer_dropdown.pack()

# Create a style for the Treeview heading to make it bold
style = ttk.Style()
style.configure("Treeview.Heading", font=("Arial", 10, "bold"), anchor="w", padding=[ 0, 20])

# Creating the Treeview Widget with bold headings
columns = ("Start Date", "End Date", "Quantity", "Used", "% Used", "Rate Table Series", "State")
line_items_table = ttk.Treeview(existing_customer_tab, columns=columns, show="headings", height=15, style="Treeview")

line_items_table.bind("<<TreeviewSelect>>", on_table_select)
line_items_table.bind("<Double-1>", lambda event: edit_line_item())  # Bind double-click event to edit_line_item

# Define column headings
for col in columns:
    line_items_table.heading(col, text=col, anchor="w")  # Align left
    line_items_table.column(col, width=120, anchor="w", stretch=True)  # Align left and allow stretching

line_items_table.pack(fill="both", expand=True, pady=20)

button_frame = tk.Frame(existing_customer_tab)
button_frame.pack(side="left", pady=10)

edit_customer_id = tk.StringVar(button_frame)
edit_button = ttk.Button(button_frame, text="Edit Line Item", command=edit_line_item, state=tk.DISABLED)
edit_button.pack(side="left", padx=10)

# Add email button 
email_button = ttk.Button(button_frame, text="Email Line Item", command=email_line_item, state=tk.DISABLED)
email_button.pack(side="left", padx=10)

# Add Delete button 
delete_button = Button(
            button_frame, 
            text="Delete Line Item", 
            command=delete_line_item,
            state=tk.DISABLED, 
            bootstyle="danger"
            )
delete_button.pack(side="left", padx=10)

# Add Reporting button 
reporting_button = Button(
            button_frame, 
            text="Reporting", 
            command=start_reporting,
            bootstyle="info"
            )
reporting_button.pack(side="left", padx=10)

# Add customer ID label to the right of the Delete Line Item button
customer_id_label = ttk.Label(button_frame, text="Instance ID: ", font=("Arial", 10, "normal"))
customer_id_label.pack(side="left", padx=30)

# Add copy button to the right of the Elastic Instance ID display
def copy_to_clipboard():
    root.clipboard_clear()
    root.clipboard_append(edit_customer_id.get())
    root.update()  # Now it stays on the clipboard after the window is closed
    messagebox.showinfo("Copied", "Elastic Instance ID copied to clipboard")

copy_button = ttk.Button(button_frame, text="Copy", command=copy_to_clipboard, width=10)
copy_button.pack(side="right", padx=10)


# Fetch and display logo
response = requests.get(config['logo_url'])
if response.status_code == 200:
    image_data = Image.open(BytesIO(response.content)).resize((250, 56), Image.Resampling.LANCZOS)
    logo_image = ImageTk.PhotoImage(image_data)
    tk.Label(rate_table_tab, image=logo_image).place(relx=0.95, y=10, anchor="ne")
    tk.Label(customer_entitlements_tab, image=logo_image).place(relx=0.95, y=10, anchor="ne")
    tk.Label(existing_customer_tab, image=logo_image).place(relx=0.95, y=10, anchor="ne")    

# Start the main event loop
# Start the main application
if __name__ == "__main__":
    logging.info("Application started.")
    try:
        root.mainloop()
    except Exception as e:
        logging.critical(f"Critical application error: {e}")
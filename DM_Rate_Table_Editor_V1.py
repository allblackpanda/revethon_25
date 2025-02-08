import tkinter as tk
from tkinter import messagebox, Toplevel, Text, Scrollbar, ttk
from PIL import Image, ImageTk
from tkcalendar import Calendar
import time
import requests
import json
import datetime
import webbrowser
import re
import uuid
from io import BytesIO
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

#Global example rate table
EXAMPLE_RATE_TABLE = [{
    "effectiveFrom": "",
    "series": "NewSeries",
    "version": "1",
    "items": [
        {
            "name": "Intermediate",
            "version": "1.0",
            "rate": 7.0},
        {
            "name": "Basic",
            "version": "1.0",
            "rate": 5.0
        },
        {
            "name": "Advanced",
            "version": "1.0",
            "rate": 10.0
        }
    ]
}]

UAT_OPTION = "-uat"

def read_config():
    config = {}
    with open("config.txt", "r") as file:
        for line in file:
            key, value = line.strip().split(" = ")
            config[key] = value
    return config

def convert_epoch_to_date(epoch_ms):
    try:
        epoch_sec = int(epoch_ms) / 1000  # Convert milliseconds to seconds
        return datetime.datetime.fromtimestamp(epoch_sec).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return "Invalid Date"
    
def convert_date_to_epoch(date_str, date_format='%Y-%m-%d %H:%M:%S'):
    try:
        dt = datetime.datetime.strptime(date_str, date_format)
        epoch_ms = int(dt.timestamp() * 1000)  # Convert seconds to milliseconds
        return epoch_ms
    except ValueError:
        return "Invalid Date Format"

# Filter out historic tables and only return the latest versions active and any future tables
def filter_series(input_series):
    current_epoch = int(time.time()) * 1000
    latest_versions = {}
    total_series = []
    for item in input_series:
        item_series = item.get("series", "")
        item_version = float(item.get("version", 0))
        effective_from = item.get("effectiveFrom", 0) if item.get("effectiveFrom") else 0

        if convert_date_to_epoch(effective_from) >= current_epoch:
            total_series.append(item) 
        elif item_series not in latest_versions or float(item_version) > float(latest_versions[item_series]["version"]):
            latest_versions[item_series] = item               
        
    total_series.extend(latest_versions.values())

    #Sort the list again
    def return_key_value(array):
        return array['series'] 
    total_series.sort(key=return_key_value, reverse=True)
    return total_series 

def get_rate_tables(filtered=False):
    #print(f'Button selected is',UAT_OPTION)
    if env_var.get() == UAT_OPTION:
        url = f"https://{config['site']}-uat.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/rate-tables"
    else:
        url = f"https://{config['site']}.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/rate-tables"
    
    headers = {
        "Authorization": f"Bearer {config['jwt']}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if not data:
            messagebox.showinfo("Info", "No Rate Tables Exist, loading an example Rate Table")
            data = [{
                "effectiveFrom": "",
                "series": "NewSeries",
                "version": "1",
                "items": [
                    {
                        "name": "Intermediate",
                        "version": "1.0",
                        "rate": 7.0
                    },
                    {
                        "name": "Basic",
                        "version": "1.0",
                        "rate": 5.0
                    },
                    {
                        "name": "Advanced",
                        "version": "1.0",
                        "rate": 10.0
                    }
                ]
            }]
        if isinstance(data, list):
            data.sort(key=lambda x: (x.get('series', ''), float(x.get('version', 0))), reverse=True)

            # Convert epoch timestamps
            for rate_table in data:
                if 'effectiveFrom' in rate_table and rate_table['effectiveFrom']:
                    rate_table['effectiveFrom'] = convert_epoch_to_date(rate_table['effectiveFrom'])
                if 'created' in rate_table and rate_table['created']:
                    rate_table['created'] = convert_epoch_to_date(rate_table['created'])

            # **Apply filtering if button was clicked**
            if filtered:
                data = filter_series(data)

        with open("rate_tables.json", "w") as file:
            json.dump(data, file, indent=4)
    else:
        messagebox.showerror("Error", f"Failed to retrieve rate tables: {response.status_code}")

    try:
        with open("rate_tables.json", "r") as file:
            data = json.load(file)
            series_window = Toplevel(root)
            series_window.title("Existing Rate Tables")
            window_width = 520  # Adjust as necessary
            window_height = 550  # Adjust as necessary
            series_window.geometry(f"{window_width}x{window_height}+{x+170}+{y+60}")

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

            series_text_area = Text(series_window, wrap="word", height=25, width=50)
            series_text_area.pack(side="top", fill="both", expand=True)

            def show_series():
                selected_series_version = series_var.get()
                selected_series, selected_version = selected_series_version.split(" - v")
                series_data = [item for item in sorted_series if item.get('series', '') == selected_series and str(item.get('version', 'N/A')) == selected_version]
                
                if series_data:
                    series_info = series_data[0]
                    formatted_output = (
                        f"Series Name:\t\t{series_info.get('series', '')}\n"
                        f"Series Version:\t\t{series_info.get('version', '')}\n\n"
                        f"   Start Date:\t\t{series_info.get('effectiveFrom', '')}\n"
                        f" Created Date:\t\t{series_info.get('created', '')}\n\n"
                        f"{'Item Name'}\t\t\t{'Version'}\t\t{'Rate'}\n"
                        f"{'-'*45}\n"
                    )
                    
                    for item in series_info.get("items", []):
                        formatted_output += (
                            f"{item.get('name', '')}\t\t\t{item.get('version', '')}\t\t{str(item.get('rate', ''))}\n"
                        )
                    
                    series_text_area.config(state="normal")
                    series_text_area.delete("1.0", "end")
                    series_text_area.insert("1.0", formatted_output)
                    series_text_area.config(state="disabled")

            def copy_to_main():
                text_data = series_text_area.get("1.0", "end").strip()  # Remove leading whitespace from entire text

                # Remove lines starting with "Created Date" (ignoring leading whitespace)
                text_data = "\n".join(
                    line for line in text_data.splitlines() 
                    if not re.match(r"^\s*Created Date", line) and "------" not in line
                )

                main_text_area.config(state="normal")
                main_text_area.delete("1.0", "end")
                main_text_area.insert("1.0", text_data)
                
                result_label.config(text="Rate table successfully copied")
                date_button.config(state=tk.ACTIVE)
                post_site_button.config(state=tk.ACTIVE)
                increment_version_button.config(state=tk.ACTIVE)
                
                series_window.destroy()

            def delete_rate_table():
                selected_series_version = series_var.get()
                selected_series, selected_version = selected_series_version.split(" - v")
                
                if env_var.get() == UAT_OPTION:
                    url = f"https://{config['site']}-uat.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/rate-tables/?series={selected_series}&version={selected_version}"
                else:
                    url = f"https://{config['site']}.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/rate-tables/?series={selected_series}&version={selected_version}"

                headers = {
                    "Authorization": f"Bearer {config['jwt']}",
                    "Content-Type": "application/json"
                }
                response = requests.delete(url, headers=headers)
                if response.status_code == 204:
                    messagebox.showinfo("Success", "Rate table deleted")
                    result_label.config(text="Rate table successfully deleted")
                    series_window.destroy()
                else:
                    if response.status_code == 409:
                        messagebox.showwarning("Warning", f"Rate Table is already in effect and cannot be deleted")
                        series_window.lift()  # Keep window in focus
                        series_window.focus_force()
    

        copy_button = tk.Button(series_window, text="Copy to Rate Table Editor", command=copy_to_main)
        copy_button.pack(side="left", padx=25, pady= 10)
        delete_button = tk.Button(series_window, text="Delete Rate Table", command=delete_rate_table, fg="red")
        delete_button.pack(side = "left", padx=10, pady=10)
        close_button = tk.Button(series_window, text="Close", command=series_window.destroy)
        close_button.pack(side="right", padx=10, pady=10)

        show_series()
    except FileNotFoundError:
        messagebox.showerror("Error", "No rate tables found.")

def select_date():
    def ok():
        selected_date = cal.selection_get()
        selected_hour = int(hour_combobox.get())
        selected_minute = int(minute_combobox.get())

        # Combine date and time
        selected_datetime = datetime.datetime(
            selected_date.year, selected_date.month, selected_date.day,
            selected_hour, selected_minute
        )
        formatted_date = selected_datetime.strftime('%Y-%m-%d %H:%M:%S')

        # Update Start Date in the currently displayed text
        text_data = main_text_area.get("1.0", "end").strip()
        if "Start Date:" in text_data:
            updated_text = ""
            for line in text_data.split("\n"):
                if line.lstrip().startswith("Start Date:"):
                    leading_spaces = len(line) - len(line.lstrip())
                    updated_text += " " * leading_spaces + f"Start Date: \t{formatted_date}\n"
                else:
                    updated_text += line + "\n"
            
            main_text_area.config(state="normal")
            main_text_area.delete("1.0", "end")
            main_text_area.insert("1.0", updated_text)
            result_label.config(text="Start Date updated Successfully")
            main_text_area.config(state="normal")
        
        top.destroy()

    top = tk.Toplevel(root)
    top.title("Select Rate Table Start Date and Time")
    top.geometry(f"{400}x{420}+{x+80}+{y+70}")
    
    today = datetime.date.today()
    now = datetime.datetime.now()  # Get the current time

    cal = Calendar(top, font="Arial 14", selectmode='day', cursor="hand1",
                   year=today.year, month=today.month, day=today.day, 
                   background='lightgreen', foreground='black',
                   bordercolor='gray', headersbackground='gray',
                   normalbackground='white', weekendbackground='lightgray', 
                   selectbackground='blue')
    cal.pack(fill="both", expand=True, padx=10, pady=10)

    # Time selection frame
    time_frame = tk.Frame(top)
    time_frame.pack(pady=10)

    tk.Label(time_frame, text="Hour:").pack(side="left", padx=5)
    hour_combobox = ttk.Combobox(time_frame, values=[str(i).zfill(2) for i in range(24)], width=3)
    hour_combobox.set(str(now.hour).zfill(2))  # Set current hour as default
    hour_combobox.pack(side="left")

    tk.Label(time_frame, text="Minute:").pack(side="left", padx=5)
    minute_combobox = ttk.Combobox(time_frame, values=[str(i).zfill(2) for i in range(60)], width=3)
    minute_combobox.set(str(now.minute).zfill(2))  # Set current minute as default
    minute_combobox.pack(side="left")

    tk.Button(top, text="Update Rate Table Start Date", command=ok).pack(pady=10)

def increment_version():
    """Increments the value of 'Series Version' in the main text UI."""
    text_data = main_text_area.get("1.0", "end").strip()
    
    if not text_data:
        messagebox.showerror("Error", "No data available to increment version.")
        return

    updated_text = ""
    for line in text_data.split("\n"):
        if line.lstrip().startswith("Series Version:"):
            leading_spaces = len(line) - len(line.lstrip())
            version_number = int(line.split("\t")[-1]) + 1 if line.split("\t")[-1].isdigit() else 1
            updated_text += " " * leading_spaces + f"Series Version:\t{version_number}\n"
        else:
            updated_text += line + "\n"
    
    main_text_area.config(state="normal")
    main_text_area.delete("1.0", "end")
    main_text_area.insert("1.0", updated_text.strip())
    main_text_area.config(state="normal")
    result_label.config(text="Series Version incremented successfully")

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

        # Write to JSON file  Enable for debug only
        #with open("new_rate_table.json", "w") as json_file:
            #json.dump(rate_table, json_file, indent=4)

        # Determine API endpoint
        base_url = f"https://{config['site']}-uat" if env_var.get() == UAT_OPTION else f"https://{config['site']}"
        api_url = f"{base_url}.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/rate-tables"

        headers = {
            "Authorization": f"Bearer {config['jwt']}",
            "Content-Type": "application/json"
        }
        response = requests.post(api_url, headers=headers, json=rate_table)

        if response.status_code in [200, 201]:
            messagebox.showinfo("Success", "Rate Table posted successfully")
        else:
            if response.status_code == 409:
                messagebox.showwarning("Warning", f"Rate Table with the specified Series and Version already exists")
    except Exception as e:
        pass
        messagebox.showerror("Error", f"Failed to process data: {str(e)}")

def open_user_guide():
    webbrowser.open("https://docs.revenera.com/dm/dynamicmonetization_ug/Content/helplibrary/DMGettingStarted.htm")
def open_api_ref():
    webbrowser.open("https://fnoapi-dynamicmonetization.redoc.ly/#operation/getRateTables")

def read_config():
    config = {}
    with open("config.txt", "r") as file:
        for line in file:
            key, value = line.strip().split(" = ")
            config[key] = value
    return config

config = read_config()

# Register Customer Function
def register_customer():
    """Registers a new customer using DAPI"""
    
    customer_id = customer_id_entry.get().strip()
    customer_name = customer_name_entry.get().strip()
    
    # Validate inputs
    if not customer_id or not customer_name:
        messagebox.showerror("Error", "Customer ID and Customer Name are required.")
        return

    # Determine API URL
    if env_var.get() == UAT_OPTION:
        url = f"https://{config['site']}-uat.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/instances"
    else:
        url = f"https://{config['site']}.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/instances"

    headers = {
        "Authorization": f"Bearer {config['jwt']}",
        "Content-Type": "application/json"
    }

    payload = {
        "shortName": customer_name,
        "accountId": customer_id
    }

    try:
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
    if env_var.get() == UAT_OPTION:
        url = f"https://{config['site']}-uat.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/rate-tables"
    else:
        url = f"https://{config['site']}.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/rate-tables"
    
    headers = {
        "Authorization": f"Bearer {config['jwt']}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        table_list = []
        for entry in data:
            if entry["series"] not in table_list:
                table_list.append(entry["series"])
        #print(table_list)
        return table_list
    else:
        messagebox.showerror("Error", f"Failed to retrieve rate tables: {response.status_code}")


def generate_uuid():
    return str(uuid.uuid4())

# After Registering, map the token line items
def map_token_line_item(instance_id):
    customer_name = customer_name_entry.get().strip()
    token_number = token_number_entry.get().strip()
    start_date = start_date_label.cget("text")
    end_date = end_date_label.cget("text")
    selected_rate_table = rate_table_var.get()
    start_epoch = convert_date_to_epoch(start_date + " 00:00:00")
    end_epoch = convert_date_to_epoch(end_date + " 23:59:59")
    
    # Call API
    # Determine API URL
    if env_var.get() == UAT_OPTION:
        url = f"https://{config['site']}-uat.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/instances/{instance_id}/line-items"
    else:
        url = f"https://{config['site']}.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/instances/{instance_id}/line-items"

    headers = {
        "Authorization": f"Bearer {config['jwt']}",
        "Content-Type": "application/json"
    }

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
            messagebox.showinfo("Success: ", f"{token_number} Tokens successfully mapped to: {customer_name}")

        else:
            messagebox.showerror("Error", f"Failed to map tokens to customer: {response.status_code}\n{response.text}")

    except Exception as e:
        messagebox.showerror("Error", f"Request failed: {str(e)}")   

# Register Customer Function
def create_and_map_customer():
    customer_id = customer_id_entry.get().strip()
    token_number = token_number_entry.get().strip()
    start_date = start_date_label.cget("text")
    end_date = end_date_label.cget("text")
    selected_rate_table = rate_table_var.get()
    if not customer_id or not token_number or not start_date or not end_date or not selected_rate_table or end_date =="Select End Date" or start_date == "Select Start Date":
        messagebox.showerror("All fields are required")
        return
    else:
        # We want to modify register customer to check if the accountId already exists and has a default instance. 
        # If it comes back, don't create a new customer instance. Instead proceed to map the token line item
        elastic_instance_id = register_customer()
        map_token_line_item(elastic_instance_id)

# Create the main application window
root = tk.Tk()
root.title("Revenera Dynamic Monetization Standalone Tool")

# Set window size and position
window_width, window_height = 770, 720
screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
x, y = (screen_width - window_width) // 2, (screen_height - window_height) // 2
root.geometry(f"{window_width}x{window_height}+{x}+{y-40}")

def on_existing_customers_tab_selected(event):
    """Update customer dropdown values when the 'Manage Existing Customers' tab is selected."""
    global customer_data
    customer_data = load_customer_names()  # Reload customer list
    
    # Update dropdown values
    customer_dropdown["values"] = [c["accountId"] for c in customer_data]
    
    # Set the first customer by default if available
    if customer_data:
        selected_account_var.set(customer_data[0]["accountId"])
    else:
        selected_account_var.set("")  # Clear selection if no customers exist

def on_env_change():
    """Reload customer names and clear the line items display when the environment selection changes."""
    global customer_data
    customer_data = load_customer_names()  # Reload customer list

    # Update the customer dropdown
    customer_dropdown["values"] = [c["accountId"] for c in customer_data]
    if customer_data:
        selected_account_var.set(customer_data[0]["accountId"])  # Set the first option
    else:
        selected_account_var.set("")  # Clear selection if no data

    # Clear the "Get Line Items" display
    line_items_text.config(state="normal")
    line_items_text.delete("1.0", "end")
    line_items_text.config(state="disabled")

def load_customer_names():
    customer_data = []
    
    if env_var.get() == UAT_OPTION:
        url = f"https://{config['site']}-uat.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/instances/?size=500"
    else:
        url = f"https://{config['site']}.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/instances/?size=500"

    headers = {
        "Authorization": f"Bearer {config['jwt']}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code in [200, 201]:
            response_data = response.json()
            instances = response_data.get("content", [])
        
            # Store customer data in an array
            customer_data = sorted([
                {"accountId": entry["accountId"], "shortName": entry["shortName"], "id": entry["id"]} 
                for entry in instances if entry.get("defaultInstance")
            ], key=lambda x: x["accountId"]) # Sort by accountId
        else:
            messagebox.showerror("Error", f"Failed to get customer list: {response.status_code}\n{response.text}")
    except Exception as e:
        messagebox.showerror("Error", f"Request failed: {str(e)}")
    return customer_data


def get_customer_line_items():
    selected_account_id = selected_account_var.get()
    selected_customer = next((c for c in customer_data if c["accountId"] == selected_account_id), None)
    
    if not selected_customer:
        messagebox.showerror("Error", "Please select a valid customer.")
        return
    
    customer_id = selected_customer["id"]
    
    if env_var.get() == UAT_OPTION:
        url = f"https://{config['site']}-uat.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/instances/{customer_id}/line-items"
    else:
        url = f"https://{config['site']}.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/instances/{customer_id}/line-items"

    headers = {"Authorization": f"Bearer {config['jwt']}", "Content-Type": "application/json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        line_items_text.config(state="normal")
        line_items_text.delete("1.0", "end")
        line_items_text.insert("1.0", json.dumps(data, indent=4))
        line_items_text.config(state="disabled")
    else:
        messagebox.showerror("Error", f"Failed to get line items: {response.status_code}")

# Create a Notebook (Tabbed Interface)
notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill="both")

# Create "Rate Table Generator" tab
rate_table_tab = ttk.Frame(notebook)
notebook.add(rate_table_tab, text="Rate Table Generator", padding= 5)

# Create "Customer Entitlements" tab
customer_entitlements_tab = ttk.Frame(notebook)
notebook.add(customer_entitlements_tab, text="Entitle New Customers", padding= 5)

# UI Components for "Rate Table Generator" tab
env_var = tk.StringVar(value=UAT_OPTION)

# Radio Buttons for Environment Selection
radio_frame = tk.Frame(rate_table_tab)
radio_frame.pack(side="top", anchor="nw", pady=30)
tk.Radiobutton(radio_frame, text="Production", variable=env_var, value="Production").pack(side="left", padx=10)
tk.Radiobutton(radio_frame, text="UAT", variable=env_var, value=UAT_OPTION).pack(side="left", padx=10)
# Tenant label
ttk.Label(rate_table_tab, text=f"Tenant: {config['site']}", font=("Arial", 10, "bold")).place(x=30, y=10)




# Buttons for Rate Table Actions
button_width = 23

# Add a new button to get filtered rate tables
filter_var = tk.BooleanVar()
ttk.Button(rate_table_tab, text="Get All Rate Tables", command=get_rate_tables, padding=(5, 7), width=button_width).place(x=10, y=120)
ttk.Button(rate_table_tab, text="Get Current/Future Tables", command=lambda: get_rate_tables(filtered=True), padding=(5, 7), width=button_width).place(x=10, y=170)
increment_version_button = ttk.Button(rate_table_tab, text="Increment Series Version", command=increment_version, padding=(5, 7), width=button_width, state=tk.DISABLED)
increment_version_button.place(x=10, y=220)
date_button = ttk.Button(rate_table_tab, text="Select New Start Date", command=select_date, padding=(5, 7), width=button_width, state=tk.DISABLED)
date_button.place(x=10, y=270)

post_site_button = ttk.Button(rate_table_tab, text="Post New Rate Table", command=post_to_site, padding=(5, 7), width=button_width, state=tk.DISABLED)
post_site_button.place(x=590, y=170)

# Text Area for Rate Table
main_text_area = Text(rate_table_tab, wrap="word", height=30, width=50)
main_text_area.pack()

# Result Label
result_label = tk.Label(rate_table_tab, text="", font=("Arial", 10, "bold"))
result_label.pack(pady=10)

# User Guide and API Reference Buttons
ttk.Button(rate_table_tab, text="Dynamic Monetization User Guide", command=open_user_guide, padding=(5, 7), width=30).place(x=10, y=645)
ttk.Button(rate_table_tab, text="Rate Table API Reference", command=open_api_ref, padding=(5, 7), width=button_width).place(x=220, y=645)

# Exit Button
ttk.Button(rate_table_tab, text="Exit", command=root.quit, padding=(5, 5)).place(x=660, y=645)

# Tenant label (Upper Left at x=30, y=10)
ttk.Label(customer_entitlements_tab, text=f"Tenant: {config['site']}", font=("Arial", 10, "bold")).place(x=30, y=10)

# Radio Buttons for Environment Selection (Moved to x=30, y=40, Left Side)
radio_frame = tk.Frame(customer_entitlements_tab)
radio_frame.pack(side="top", anchor="nw", pady=30)

tk.Radiobutton(radio_frame, text="Production", variable=env_var, value="Production").pack(side="left", padx=10)
tk.Radiobutton(radio_frame, text="UAT", variable=env_var, value=UAT_OPTION).pack(side="left", padx=10)

# Create a frame for better layout management
customer_frame = tk.Frame(customer_entitlements_tab)
customer_frame.place(x=30, y=120)  # Position below the environment selection

# Customer ID Label and Entry (Left side)
ttk.Label(customer_frame, text="Customer ID:", font=("Arial", 10, "normal")).pack(side="left", padx=5)
customer_id_entry = ttk.Entry(customer_frame, width=20)
customer_id_entry.pack(side="left", padx=5)

# Customer Name Label and Entry (Right of Customer ID)
ttk.Label(customer_frame, text="Customer Name:", font=("Arial", 10, "normal")).pack(side="left", padx=5)
customer_name_entry = ttk.Entry(customer_frame, width=25)
customer_name_entry.pack(side="left", padx=5)


def open_calendar(label):
    def set_date():
        selected_date = cal.selection_get().strftime('%Y-%m-%d')
        label.config(text=selected_date)
        top.destroy()
    
    top = Toplevel(root)
    top.title("Select Date")
    top.geometry(f"{400}x{420}+{x+80}+{y+70}")
    today = datetime.date.today()
    # now = datetime.datetime.now()  # Get the current time
    cal = Calendar(top, font="Arial 14", selectmode='day', cursor="hand1",
                   year=today.year, month=today.month, day=today.day, 
                   background='lightgreen', foreground='black',
                   bordercolor='gray', headersbackground='gray',
                   normalbackground='white', weekendbackground='lightgray', 
                   selectbackground='blue')
    cal.pack(pady=10)
    ttk.Button(top, text="Select", command=set_date).pack()

# Create extra frame for better layout management
entry_frame = tk.Frame(customer_entitlements_tab)
entry_frame.place(x=30, y=180) 

ttk.Label(entry_frame, text="Rate Table:", font=("Arial", 10, "normal")).pack(side="left", padx=5)
rate_table_var = tk.StringVar()

rate_table_list = get_rate_tables_names()
if rate_table_list:
    rate_table_var.set(rate_table_list[0])
rate_table_dropdown = ttk.Combobox(entry_frame, textvariable=rate_table_var, values=rate_table_list, width=25)
rate_table_dropdown.state(['readonly'])
rate_table_dropdown.pack(side="left", padx=5)
ttk.Label(entry_frame, text="Number of Tokens:", font=("Arial", 10, "normal")).pack(side="left", padx=5)

def validate_token_input(P):
    return P.isdigit() and int(P) > 0 if P else True

vcmd = (entry_frame.register(validate_token_input), "%P")

token_number_entry = ttk.Entry(entry_frame, width=30, font=("Arial", 10, "normal"), validate="key", validatecommand=vcmd)
token_number_entry.pack(side="left", padx=5)

start_date_frame = tk.Frame(customer_entitlements_tab)
start_date_frame.place(x=30, y=230) 

ttk.Label(start_date_frame, text="Start Date:", font=("Arial", 10, "normal")).pack(side="left", padx=5)

start_date_label = ttk.Label(start_date_frame, text="Select Start Date", background="lightgray", font=("Arial", 10, "normal"), width=15)
start_date_label.pack(side="left", padx=5)

ttk.Button(start_date_frame, text="Pick Date", command=lambda: open_calendar(start_date_label)).pack(side="left", padx=5)

end_date_frame = tk.Frame(customer_entitlements_tab)
end_date_frame.place(x=30, y=280) 

ttk.Label(end_date_frame, text="End Date:", font=("Arial", 10, "normal")).pack(side="left", padx=5)

end_date_label = ttk.Label(end_date_frame, text="Select End Date", background="lightgray", font=("Arial", 10, "normal"), width=15)
end_date_label.pack(side="left", padx=9)

ttk.Button(end_date_frame, text="Pick Date", command=lambda: open_calendar(end_date_label)).pack(side="left", padx=5)

create_frame = tk.Frame(customer_entitlements_tab)
create_frame.place(x=30, y=330)

generate_button = ttk.Button(create_frame, text="Create & Entitle Customer", command=create_and_map_customer, padding=(5, 7), width=28)
generate_button.pack(padx=10)

map_label = ttk.Label(create_frame, text="", wraplength=400)
map_label.pack()

# Exit Button (Bottom Right)
ttk.Button(customer_entitlements_tab, text="Exit", command=root.quit, padding=(5, 5)).place(x=660, y=645)

# Create "Manage Existing Customers" tab
existing_customer_tab = ttk.Frame(notebook)
notebook.add(existing_customer_tab, text="Manage Existing Customers", padding=5)

# Tenant label (Upper Left at x=30, y=10)
ttk.Label(existing_customer_tab, text=f"Tenant: {config['site']}", font=("Arial", 10, "bold")).place(x=30, y=10)

# Radio Buttons for Environment Selection (Updated)
radio_frame = tk.Frame(existing_customer_tab)
radio_frame.pack(side="top", anchor="nw", pady=30)

tk.Radiobutton(radio_frame, text="Production", variable=env_var, value="Production", command=on_env_change).pack(side="left", padx=10)
tk.Radiobutton(radio_frame, text="UAT", variable=env_var, value=UAT_OPTION, command=on_env_change).pack(side="left", padx=10)


# UI Components for "Manage Existing Customer" tab

# Bind the function to tab selection
notebook.bind("<<NotebookTabChanged>>", on_existing_customers_tab_selected)

# Load customers and update UI
ttk.Label(existing_customer_tab, text="Select Customer (Account ID):").pack()
customer_data = load_customer_names()
selected_account_var = tk.StringVar(existing_customer_tab)

if customer_data:
    selected_account_var.set(customer_data[0]["accountId"])
customer_dropdown = ttk.Combobox(existing_customer_tab, textvariable=selected_account_var,
                                 values=[c["accountId"] for c in customer_data], width=40, state='readonly', height=70)
customer_dropdown.bind("<<ComboboxSelected>>", lambda event: get_customer_line_items())
customer_dropdown.pack()


ttk.Label(existing_customer_tab, text="Customer Line Items:").pack()
line_items_text = Text(existing_customer_tab, wrap="word", height=25, width=80)
line_items_text.pack()

# Exit Button (Bottom Right)
ttk.Button(existing_customer_tab, text="Exit", command=root.quit, padding=(5, 5)).place(x=660, y=645)

# Fetch and display logo
logo_url = "https://flex1107-esd.flexnetoperations.com/flexnet/operations/WebContent?fileID=revenera_logo"
response = requests.get(logo_url)
if response.status_code == 200:
    image_data = Image.open(BytesIO(response.content)).resize((200, 39), Image.Resampling.LANCZOS)
    logo_image = ImageTk.PhotoImage(image_data)
    tk.Label(rate_table_tab, image=logo_image).place(relx=0.95, y=10, anchor="ne")
    tk.Label(customer_entitlements_tab, image=logo_image).place(relx=0.95, y=10, anchor="ne")
    tk.Label(existing_customer_tab, image=logo_image).place(relx=0.95, y=10, anchor="ne")    

root.mainloop()
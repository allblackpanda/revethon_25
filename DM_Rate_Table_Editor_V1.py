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
from io import BytesIO

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
    if env_var.get() == "-uat":
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
                
                if env_var.get() == "-uat":
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
        base_url = f"https://{config['site']}-uat" if env_var.get() == "-uat" else f"https://{config['site']}"
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

# Create the main application window
root = tk.Tk()
root.title("Revenera Dynamic Monetization Tool")

# Set window size and position
window_width, window_height = 750, 720
screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
x, y = (screen_width - window_width) // 2, (screen_height - window_height) // 2
root.geometry(f"{window_width}x{window_height}+{x}+{y-40}")

# Create a Notebook (Tabbed Interface)
notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill="both")

# Create "Rate Table Generator" tab
rate_table_tab = ttk.Frame(notebook)
notebook.add(rate_table_tab, text="Rate Table Generator")

# Create "Customer Entitlements" tab
customer_entitlements_tab = ttk.Frame(notebook)
notebook.add(customer_entitlements_tab, text="Customer Entitlements")

# UI Components for "Rate Table Generator" tab
env_var = tk.StringVar(value="-uat")

# Radio Buttons for Environment Selection
radio_frame = tk.Frame(rate_table_tab)
radio_frame.pack(side="top", anchor="nw", pady=30)
tk.Radiobutton(radio_frame, text="Production", variable=env_var, value="Production").pack(side="left", padx=10)
tk.Radiobutton(radio_frame, text="UAT", variable=env_var, value="-uat").pack(side="left", padx=10)

# Fetch and display logo
logo_url = "https://flex1107-esd.flexnetoperations.com/flexnet/operations/WebContent?fileID=revenera_logo"
response = requests.get(logo_url)
if response.status_code == 200:
    image_data = Image.open(BytesIO(response.content)).resize((200, 39), Image.Resampling.LANCZOS)
    logo_image = ImageTk.PhotoImage(image_data)
    tk.Label(rate_table_tab, image=logo_image).place(relx=0.95, y=10, anchor="ne")

# Tenant label
ttk.Label(rate_table_tab, text=f"Tenant: {config['site']}", font=("Arial", 10, "bold")).place(x=30, y=10)

# Buttons for Rate Table Actions
button_width = 23

# Add a new button to fetch filtered rate tables
filter_var = tk.BooleanVar()
ttk.Button(rate_table_tab, text="Get All Rate Tables", command=get_rate_tables, padding=(5, 7), width=button_width).place(x=10, y=120)
ttk.Button(rate_table_tab, text="Get Current/Future Tables", command=lambda: get_rate_tables(filtered=True), padding=(5, 7), width=button_width).place(x=10, y=170)
increment_version_button = ttk.Button(rate_table_tab, text="Increment Series Version", command=increment_version, padding=(5, 7), width=button_width, state=tk.DISABLED)
increment_version_button.place(x=10, y=220)
date_button = ttk.Button(rate_table_tab, text="Select New Start Date", command=select_date, padding=(5, 7), width=button_width, state=tk.DISABLED)
date_button.place(x=10, y=270)

post_site_button = ttk.Button(rate_table_tab, text="Post New Rate Table", command=post_to_site, padding=(5, 7), width=button_width, state=tk.DISABLED)
post_site_button.place(x=585, y=170)

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
ttk.Button(rate_table_tab, text="Exit", command=root.quit, padding=(5, 5)).place(x=650, y=645)

# Customer Entitlements Tab - Placeholder for Future Development
ttk.Label(customer_entitlements_tab, text="Customer Entitlements Features Coming Soon!", font=("Arial", 12, "bold")).pack(pady=50)

root.mainloop()
import tkinter as tk
from tkinter import messagebox, Toplevel, Text, Scrollbar, ttk
from PIL import Image, ImageTk
from tkcalendar import Calendar
import time
import requests
import json
import datetime
import webbrowser
from io import BytesIO

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

def get_rate_tables():
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
        if not data:  # Check if the data is empty
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
        with open("rate_tables.json", "w") as file:
            json.dump(data, file, indent=4)
    else:
        messagebox.showerror("Error", f"Failed to retrieve rate tables: {response.status_code}")
    
    try:
        with open("rate_tables.json", "r") as file:
            data = json.load(file)
            series_window = Toplevel(root)
            series_window.title("Existing Rate Tables")
            window_width = 420  # Adjust as necessary
            window_height = 600  # Adjust as necessary
            series_window.geometry(f"{window_width}x{window_height}+{x+170}+{y+60}")

            series_label = tk.Label(series_window, text="Select a Rate Table Series and Version:", padx=0, pady=5)
            series_label.pack()

            series_var = tk.StringVar(series_window)
            sorted_series = sorted(data, key=lambda x: (x.get('series', ''), float(x.get('version', 0))), reverse=True)
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
                series_text_area.config(state="normal")
                series_text_area.delete("1.0", "end")
                series_text_area.insert("1.0", json.dumps(series_data, indent=4))
                series_text_area.config(state="disabled")

            def copy_to_main():
                text_data = series_text_area.get("1.0", "end").strip()
                if text_data.startswith("[") and text_data.endswith("]"):
                    text_data = text_data[1:-1].strip()
                text_data = "\n".join([line for line in text_data.split("\n") if "\"created\"" not in line])
                text_data = text_data.rstrip()  # Ensure no whitespace before the last "}"
                main_text_area.config(state="normal")
                main_text_area.delete("1.0", "end")
                main_text_area.insert("1.0", text_data)
                main_text_area.config(state="normal")
                result_label.config(text="Rate table successfully copied")
                date_button.config(state=tk.ACTIVE)
                post_site_button.config(state=tk.ACTIVE)
                increment_version_button.config(state=tk.ACTIVE)
                series_window.destroy()
                
                # Extract effectiveFrom and display converted date
                try:
                    series_data = json.loads(text_data)
                    if isinstance(series_data, dict) and "effectiveFrom" in series_data:
                        formatted_date = convert_epoch_to_date(series_data["effectiveFrom"])
                        result_label.config(text=f"Displayed Rate Table Effective From Date:  {formatted_date}")

                except json.JSONDecodeError:
                    messagebox.showerror("Error", "Invalid JSON format in the text area.")

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
        timestamp = int(selected_datetime.timestamp()) * 1000  # Convert to milliseconds

        effective_from_label.config(text=f"Effective From: {timestamp}")

        # Update effectiveFrom in the currently displayed series
        text_data = main_text_area.get("1.0", "end").strip()
        if text_data:
            try:
                series_data = json.loads(text_data)
                if isinstance(series_data, dict) and "effectiveFrom" in series_data:
                    series_data["effectiveFrom"] = timestamp
                updated_text = json.dumps(series_data, indent=4)
                main_text_area.config(state="normal")
                main_text_area.delete("1.0", "end")
                main_text_area.insert("1.0", updated_text)
                main_text_area.config(state="normal")
                
                # Display the formatted date and time
                formatted_date = selected_datetime.strftime('%Y-%m-%d %H:%M:%S')
                result_label.config(text=f"Rate Table Start Date: {formatted_date}")

            except json.JSONDecodeError:
                messagebox.showerror("Error", "Failed to update effectiveFrom Start Date in the displayed series.")
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
    """Increments the version of the first 'version' field found in the main text area."""
    text_data = main_text_area.get("1.0", "end").strip()
    
    if not text_data:
        messagebox.showerror("Error", "No data available to increment version.")
        return

    try:
        series_data = json.loads(text_data)

        if isinstance(series_data, dict) and "version" in series_data:
            series_data["version"] = str(int(series_data["version"]) + 1)  # Increment version
        elif isinstance(series_data, list) and series_data:
            for item in series_data:
                if "version" in item:
                    item["version"] = str(int(item["version"]) + 1)  # Increment version of first occurrence
                    break  # Stop after first modification

        updated_text = json.dumps(series_data, indent=4)
        main_text_area.config(state="normal")
        main_text_area.delete("1.0", "end")
        main_text_area.insert("1.0", updated_text)
        main_text_area.config(state="normal")

        result_label.config(text="Series Version incremented successfully")

    except (json.JSONDecodeError, ValueError):
        messagebox.showerror("Error", "Failed to increment version. Ensure valid JSON structure.")

def post_to_site():
    """Posts the current contents of the Main UI to the configured site."""
    text_data = main_text_area.get("1.0", "end").strip()
    if not text_data:
        messagebox.showerror("Error", "No data to post.")
        return
    try:
        series_data = json.loads(text_data)

        if env_var.get() == "-uat":
            url = f"https://{config['site']}-uat.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/rate-tables"
        else:
            url = f"https://{config['site']}.flexnetoperations.{config['geo']}/dynamicmonetization/provisioning/api/v1.0/rate-tables"

        headers = {
            "Authorization": f"Bearer {config['jwt']}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, headers=headers, json=series_data)
        if response.status_code in [200, 201]:
            messagebox.showinfo("Success", "Rate Table posted successfully")
        else:
            messagebox.showerror("Error", f"Failed to post Rate Table: {response.status_code}\n{response.text}")
    except json.JSONDecodeError:
        messagebox.showerror("Error", "Invalid JSON format in the text area.")

def open_user_guide():
    webbrowser.open("https://docs.revenera.com/dm/dynamicmonetization_ug/Content/helplibrary/DMGettingStarted.htm")
def open_api_ref():
    webbrowser.open("https://fnoapi-dynamicmonetization.redoc.ly/#operation/getRateTables")

config = read_config()

root = tk.Tk()
root.title("Revenera Dynamic Monetization Token Rate Table Editor")

# Get the screen width and height
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

# Get the window width and height
window_width = 750
window_height = 720

# Calculate the x and y coordinates for the window
x = int((screen_width / 2) - (window_width / 2))
y = int((screen_height / 2) - (window_height / 2))

# Set the window geometry
root.geometry(f"{window_width}x{window_height}+{x}+{y-40}")

# Add radio buttons for Production and UAT at the top of the main window

env_var = tk.StringVar(value="-uat")  # Set UAT as default
radio_frame = tk.Frame(root)
radio_frame.pack(side="top",anchor="nw", pady=40)
prod_radio = tk.Radiobutton(radio_frame, text="Production", variable=env_var, value="Production")
prod_radio.pack(side="left", padx=10)
uat_radio = tk.Radiobutton(radio_frame, text="UAT", variable=env_var, value="-uat")
uat_radio.pack(side="left", padx=10)

# Fetch and display logo at the top of the main window
logo_url = "https://flex1107-esd.flexnetoperations.com/flexnet/operations/WebContent?fileID=revenera_logo"


response = requests.get(logo_url)
if response.status_code == 200:
    image_data = Image.open(BytesIO(response.content))
    image_data = image_data.resize((200, 39), Image.Resampling.LANCZOS)
    logo_image = ImageTk.PhotoImage(image_data)
    logo_label = tk.Label(root, image=logo_image)
    logo_label.place(relx=0.95, y=15, anchor="ne")

sitelabel = ttk.Label(root, text=f"Tenant: {config['site']}", font=("Arial", 10, "bold"))
sitelabel.place(x=30, y=15)

button_width = 23 # Fixed width for Buttons

rate_table_button = ttk.Button(root, text="Get Existing Rate Tables", command=get_rate_tables, padding=(5, 7), width=button_width)
rate_table_button.place(x=10, y=275)

date_button = ttk.Button(root, text="Select New Start Date", command=select_date, padding=(5, 7), width=button_width)
date_button.config(state=tk.DISABLED)
date_button.place(x=10, y=325)

increment_version_button = ttk.Button(root, text="Increment Series Version", command=increment_version, padding=(5, 7), width=button_width)
increment_version_button.config(state=tk.DISABLED)
increment_version_button.place(x=10, y=375)

effective_from_label = tk.Label(root, text="Effective From: ")
#effective_from_label.pack(padx=5, pady=2)

post_site_button = ttk.Button(root, text="Post New Rate Table", command=post_to_site, padding=(5, 7), width=button_width)
post_site_button.config(state=tk.DISABLED)
post_site_button.place(x=585, y=325)

main_text_area = Text(root, wrap="word", height=30, width=50)
main_text_area.pack()

result_label = tk.Label(root, text="", font=("Arial", 10, "bold"))
result_label.pack(pady=25)

style = ttk.Style()
style.configure("My.TButton", background = "red")

user_guide_button = ttk.Button(root, text="Dynamic Monetization User Guide", command=open_user_guide, padding=(5, 7), width=30)
user_guide_button.place(x=10, y=675)  # Position it at the bottom-left

user_guide_button = ttk.Button(root, text="Rate Table API Reference", command=open_api_ref, padding=(5, 7), width=button_width)
user_guide_button.place(x=220, y=675)  # Position it at the bottom-left

exit_button = ttk.Button(root, text="Exit", command=root.quit, padding=(5, 5))
exit_button.place(x=650, y=675)

root.mainloop()

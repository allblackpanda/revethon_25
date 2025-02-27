# Elastic Access Standalone Tool

## Overview

Elastic Access Standalone Tool is a GUI-based application designed to manage rate tables for dynamic monetization. The tool allows users to create, edit, delete, and post rate tables through an intuitive interface. It integrates with external APIs and provides additional functionalities such as customer entitlement management and reporting.

## Features

- **GUI-based rate table management** using Tkinter and ttkbootstrap.
- **Retrieve, create, edit, and delete rate tables** stored in JSON format.
- **API Integration** for fetching and posting rate tables.
- **Logging support** to track function calls and errors.
- **Configurable environment settings** for UAT and production.
- **Customer entitlement management** to allocate tokens and track usage.
- **Reporting module** (via `Reporting.py`) to visualize token usage data.

## Requirements

- Python 3.x
- Dependencies:
  ```sh
  pip install -r requirements.txt
  ```
- Additional setup:
  - Ensure `config.json` is present and configured correctly.
  - Chrome must be installed for automatic dashboard launching.

## Installation

1. Clone or download the repository.
2. Install the required dependencies.
3. Place the `config.json` file in the root directory.
4. Run the application with a specific configuration:
   ```sh
   python Elastic_Access_Standalone_Tool.py -config your_config
   ```

## Configuration

The application reads settings from `config.json`, which must include:

```json
{
    "site": "your_site",
    "geo": "region",
    "jwt": "path_to_jwt_file",
    "basic_Auth": "base64_encoded_username_password",
    "port": 5000,
    "theme": "default",
    "logo_url": "your_logo_url",
    "from_email": "your_email@example.com",
    "email_pwd": "your_email_password",
    "smtp_server": "your_smtp_server"
}
```

The `-config` parameter allows you to specify a configuration profile within `config.json`. The application will attempt to read and apply the corresponding settings. If the specified configuration is not found, it will default to a predefined profile.

Your `jwt`.txt will be used for authentication and should correspond to a valid administrative public key in the Dynamic Monetization tenant

The `basic_Auth` variable is used for the reporter and is required to authenticate and retrieve the usage data.

### Email Configuration

For email notification functionality, the following parameters must be included in `config.json`:
- **`from_email`**: The sender's email address.
- **`email_pwd`**: The password or app-specific password for authentication.
- **`smtp_server`**: The SMTP server address for sending emails.

Without these parameters, email notifications will not function correctly.

### Not Using Email Configuration

If you do not want to use the email function these are the required parameters in your `config.json`:
```json
{
    "site": "your_site",
    "geo": "region",
    "jwt": "path_to_jwt_file",
    "port": 5000,
    "theme": "default",
    "logo_url": "your_logo_url",
    "email_enabled": false
}
```

The parameter `email_enabled` is required to disable email notifications.

## Usage

### Running the Application

Start the application using:

```sh
python Elastic_Access_Standalone_Tool.py -config your_config
```

### Managing Rate Tables

- **Get All Rate Tables**: Fetch and display all available rate tables.
- **Get Current/Future Tables**: Filter rate tables based on their effective date.
- **Increment Version**: Increase the version number of an existing rate table.
- **Set Start Date**: Select an effective date for a rate table.
- **Post Rate Table**: Upload a modified rate table to the server.

### Customer Entitlements

- **Create & Entitle Customer**: Register a customer and allocate tokens.
- **Edit/Delete Existing Entitlements**: Modify or remove token allocations.
- **Generate Reports**: View usage data in an interactive dashboard.

## Reporting Module

A separate reporting module (`Reporting.py`) provides visualization for token usage data. To run it manually:

```sh
python Reporting.py -config default
```

Then open `http://127.0.0.1:{port}` in a browser. The `port` should be specified in your `config.json`, otherwise it will default to 5000.

### Overview of `Reporting.py`

`Reporting.py` is a Flask-based web application that retrieves and displays token usage data in an interactive format. It integrates with the API to fetch usage reports and presents them using data visualization tools like Plotly. The module allows users to filter reports based on date range and environment (UAT/Production).

#### Features:
- Fetches token usage data from the API.
- Displays reports using interactive charts.
- Allows filtering based on account and date range.
- Provides insights into token consumption and allocation trends.

## Logging

- Logs are stored in `rate_table_editor.log`.
- Errors and API responses are logged for debugging.

## Troubleshooting

- Ensure `config.json` is correctly formatted.
- Check `rate_table_editor.log` for errors.
- Verify API connectivity by testing the endpoints manually.

## License

This project is licensed under the MIT License.


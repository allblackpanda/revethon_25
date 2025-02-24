# revethon_25
Revethon Project 2025

basic_Auth is used for the reporter.py

The jwt. is used for all the dynamic monetization API calls, You'll need to have a private/public key pair created and the public key should be uploaded to your site for both UAT and Prod.
If you need assistance with this, reach out to engineering for Revenera. For all SEs, your tenants should be configured already with a public key for all SEs.

run the following command to install all the requirements:
pip install -r requirements.txt

To run the full application run the following command:
python DM_Rate_Table_Editor_V1.py -config CONFIG_OPTION

Config Option:
By default, if no config option is selected it will run the default config in config.json. Otherwise it will search for the config option name you specify on the command line.
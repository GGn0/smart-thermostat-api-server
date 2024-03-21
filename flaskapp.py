# flaskapp.py

from flask import Flask, render_template
from functools import wraps
from secrets import token_urlsafe
import yaml
import requests, binascii, secrets
from pymongo import MongoClient
from dateutil.parser import parse
from json import loads
from os import environ
from os.path import exists

# CONSTANTS
DEBUG = environ.get('DEBUG',False)
CFG_PATH = "config/config.yml"
USER_NAME = environ['USER_NAME']
PASSWORD = environ['PASSWORD']
DB_NAME = environ['DB_NAME']
CLUSTER_URL = environ['CLUSTER_URL']
THERMOSTAT_DATA_NAME = environ['THERMOSTAT_DATA_NAME']
SENSOR_DATA_NAME = environ['SENSOR_DATA_NAME']

if DEBUG:
    print(f"""Loaded env variables:
DEBUG = {DEBUG}
CFG_PATH = {CFG_PATH}
USER_NAME = {USER_NAME}
PASSWORD = {PASSWORD}
DB_NAME = {DB_NAME}
CLUSTER_URL = {CLUSTER_URL}
THERMOSTAT_DATA_NAME = {THERMOSTAT_DATA_NAME}
SENSOR_DATA_NAME = {SENSOR_DATA_NAME}

""")

# Global db variables
# Connect to mongo server
client = MongoClient(f"mongodb+srv://{USER_NAME}:{PASSWORD}@{CLUSTER_URL}/{DB_NAME}")
thermostatData = client[DB_NAME][THERMOSTAT_DATA_NAME]
sensorData = client[DB_NAME][SENSOR_DATA_NAME]

# app instance
app = Flask(__name__)

# read config file
if exists(CFG_PATH):
    cfg = yaml.safe_load(open(CFG_PATH))
else:
    # Generating random Admin API
    cfg = {"ADMIN_API": token_urlsafe(25), "API_keys": []}
    with open(CFG_PATH, 'w+') as f:
        yaml.safe_dump(cfg, f)

print(f"""

###### ADMIN KEY ######
{cfg['ADMIN_API']}
#######################



Active endpoints:

o /
	To test the server availability

o /upload/API_key=<api_key>/dev=<device_id>/data=<encoded_json>
	To upload new data to the database

o /add_token/API_key=<api_key>
	To issue a random application API. Requires the admin API

""")

if DEBUG:
    print("config loaded!")
    print(cfg)

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        # ensure the api is valid
        if kwargs['api_key'] not in (cfg['API_keys'] + [cfg['ADMIN_API']]):
            return "404 - User not found!"
        return f(*args, **kwargs)
    return decorator

def admin_login_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        # ensure the api is valid
        if kwargs['api_key'] not in [cfg['ADMIN_API']]:
            return "404 - User not found!"
        return f(*args, **kwargs)
    return decorator

# json data parser
def parse_data(encoded_json):
    decoded_json = binascii.a2b_base64(encoded_json).decode('utf-8')
    decoded_json = loads(decoded_json)

    if DEBUG:
        print(decoded_json)

    # {
    #   "date": "2024-01-01T08:00",
    #   "temp_in_C": 18,
    #   "temp_out_C": 20,
    #   "comm_status": 0,
    #   "next_set_time_s": 120,
    #   "next_set_temp": 21,
    #   "humidity_perc": 50,
    #   "rain_out": 1,
    #   "wind_spd_ms": 1.5
    # }

    date = parse(decoded_json['date'])

    try:
        parsed_json_sensor = {
            "dateTime": date,
            "tempIn": int(decoded_json['temp_in_C']*10),
            "tempOut": int(decoded_json['temp_out_C']*10),
            "rainOut": decoded_json['rain_out']==1,
            "windSpeedMs": int(decoded_json['wind_spd_ms']*10),
            "humOutPerc": int(decoded_json['humidity_perc']*10)
        }
    except:
        parsed_json_sensor = None

    try:
        parsed_json_command = {
            "dateTime": date,
            "thermostat": int(decoded_json['comm_status'])
        }
    except:
        parsed_json_command = None

    return [parsed_json_sensor, parsed_json_command]

# create root (testing only)
@app.route("/")
def main_root():
    #r = requests.get('localhost:5000/index.html')

    return("hello world!")

# create upload to db route
@app.route("/upload/API_key=<api_key>/dev=<device_id>/data=<encoded_json>")
@login_required
def upload_data(api_key, device_id, encoded_json):
    # on client side encode:
    # json_str = ujson.dumps(data_dict).encode('utf-8')
    # encoded_json = ubinascii.b2a_base64(json_str).decode('ascii')[:-1]
    # es. encoded_json = "eyJkYXRlIjogIjIwMjQtMDEtMDEiLCAidGVtcF9pbiI6IDE4LCAidGVtcF9vdXQiOiAyMCwgImNvbW1fc3RhdHVzIjogIk9OX3Jpc2luZyIsICJuZXh0X3NldF90aW1lIjogMTIwLCAibmV4dF9zZXRfdGVtcCI6IDIxfQ=="
    # global thermostatData
    # global sensorData

    [send_dict_sens, send_dict_comm] = parse_data(encoded_json)

    if send_dict_sens is not None:
        # Add sensor data to db
        sensorData.insert_one(send_dict_sens)
    elif DEBUG:
        print("\nCould not retrieve all sensor data!\n")

    if send_dict_comm is not None:
        # Add thermostat data to db
        thermostatData.insert_one(send_dict_comm)
    elif DEBUG:
        print("\nCould not retrieve all thermostat data!\n")

    return f"Authenticated<br>Device: {device_id}<br><br>Sending sensor:<br>{send_dict_sens}<br><br>Sending command feedback:<br>{send_dict_comm}"

# add an upload token
@app.route("/add_token/API_key=<api_key>")
@admin_login_required
def add_key(api_key):

    new_key = token_urlsafe(10)
    cfg['API_keys'] += [new_key]

    if DEBUG:
        print(f"""
new API_key requested by:
ADMIN: {api_key}
generated user key: {new_key}
""")

    with open(CFG_PATH, 'w+') as f:
        yaml.safe_dump(cfg, f)

    if DEBUG:
        print(f"\nConfig file updated!\n\n")

    return(new_key)


if __name__ == "__main__":

    app.run(host="0.0.0.0")

# EOF

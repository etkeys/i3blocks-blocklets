#!/usr/bin/env python3


import configparser
import json
from os import environ
import pyowm
import requests
import subprocess

_TEMP_UNIT_ = 'fahrenheit'

constants = ""
accuApiKey = ""
owmApiKey = ""

def Main():
    Setup()
    #HandleBlockButton()
    statusMessage = GetStatusBarMessage()
    print(statusMessage)

def Setup():
    global accuApiKey
    global constants
    global owmApiKey

    config = configparser.ConfigParser()
    config.read("%s/.config/my-configs/api_keys.ini" % environ["HOME"])

    with open(str("%s/bin/i3blocks/block-constants.json" % environ["HOME"])) as j:
        constants = json.load(j)

    # api keys
    accuApiKey = config["weather"]["ACCUWEATHER_API_KEY"]
    owmApiKey = config["weather"]["OWM_API_KEY"]

def HandleBlockButton():
    try:
        button = environ["BLOCK_BUTTON"]
    except:
        button = ""

    # print("Block button: %s" % button)

def GetStatusBarMessage():
    global owmApiKey
    result = ""

    if not IsInternetConnected() :
        result = str("--\u2109 --")
        return result 

    # Get the current of this computer
    # FIXME How to get the location of the system without contacting the interet?
    locrequest = requests.get("https://ipinfo.io").json()
    loc = {
        "lat": float(locrequest["loc"].split(',')[0]),
        "lon": float(locrequest["loc"].split(',')[1])
    }

    owm = pyowm.OWM(owmApiKey)
    weather = owm.weather_at_coords(loc["lat"], loc["lon"]).get_weather();

    #print("Status: %s" % weather.get_status())
    #print("Temp: %s\u2109" % int(weather.get_temperature(_TEMP_UNIT_)["temp"]))
    
    result = str("%s\u2109  %s" % (int(weather.get_temperature(_TEMP_UNIT_)["temp"]),
                                    weather.get_status()))
    
    return result

def IsInternetConnected():
    result = False

    output = subprocess.run(["ping", "-c", "1", "1.1.1.1"],
                            timeout=2.0,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            encoding="utf-8").stderr

    result = ("network is unreachable" not in output.lower())

    return result


if __name__ == "__main__":
    Main()
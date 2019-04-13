#!/usr/bin/env python3

import configparser
import json
from os import getenv
import requests
from string import Template
import subprocess

_DEFAULT_STATUS_MESSAGE_ = "--:--"

_GOOGLEMAPS_API_ADDRESS_ = "https://maps.googleapis.com/maps/api/distancematrix/json?units=imperial&mode=driving&departure_time=now&key=$gmpApiKey&origins=$origin&destinations=$destination"

_LOCATION_DEFINITION_FILE_ = "%s/.config/my-configs/travel-destinations.ini" % getenv("HOME")


def Main():
    if IsInternetConnected():
        Setup()
        HandleBlockButton()
        print(GetStatusMessage())
    else:
        print(_DEFAULT_STATUS_MESSAGE_)


def IsInternetConnected():
    result = False

    output = subprocess.run(["ping", "-c", "1", "1.1.1.1"],
                            timeout=2.0,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            encoding="utf-8").stderr.lower()

    result = ("network is unreachable" not in output)

    return result


def Setup():
    gbls = globals()

    with open(str("%s/bin/i3blocks/block-constants.json" % getenv("HOME"))) as j:
        gbls["constants"] = json.load(j)

    config = configparser.ConfigParser()
    config.read("%s/.config/my-configs/api_keys.ini" % getenv("HOME"))

    # api keys
    gbls["gmpApiKey"] = config["travel"]["GOOGLE_MAPS_PLATFORM_API_KEY"]

    # origin locatin
    gbls["origin"] = requests.get("https://ipinfo.io/loc").text.strip()

    # destination location
    config = configparser.ConfigParser()
    config.read(_LOCATION_DEFINITION_FILE_)

    gbls["destination"] = config["DEFAULT"]["work"]


def HandleBlockButton():
    pass

def GetStatusMessage():
    result = _DEFAULT_STATUS_MESSAGE_

    reqUrl = Template(_GOOGLEMAPS_API_ADDRESS_).safe_substitute(globals())

    request = requests.get(reqUrl).json()

    result = "%s" % request["rows"][0]["elements"][0]["duration_in_traffic"]["text"]

    return result

if __name__ == "__main__":
    Main()

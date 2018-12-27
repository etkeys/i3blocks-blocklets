#!/usr/bin/env python3

import configparser
import datetime
import json
from os import getenv
import requests
from string import Template
import subprocess

_DARKSKY_API_ADDRESS_ = "https://api.darksky.net/forecast/$apikey/$lat,$lon?units=us&exclude=$exclude_blocks"

_DATE_STR_FORMAT_ = '%a %b %d, %Y'
_DATE_STR_FORMAT_WITH_TIME_ = '%l:%M %p %a %b %d, %Y'

_DAY_FORECAST_TEMPLATE_="""
$date
$condition
$temp_l\u2109 ($temp_al\u2109 ) - $temp_h\u2109 ($temp_ah\u2109 )
Precip: ${precip}%
Wind: $wind ($windg) mph
"""

_HOUR_FORECAST_TEMPLATE_ = """
$time
$temp - $condition
Precip: ${precip}%
Wind: $wind ($windg) mph
"""

# Factor to gauge if the difference between
# DarkSky temperature and apperent temperature
# (what it feels like) is significant. Value is
# in degrees F.
_TEMP_APPARENT_TEMP_SIGNIFICANCE_DIFF_ = 5

_TEMP_UNIT_ = 'fahrenheit'

_WEATHER_FORECAST_TMP_FILE_="/tmp/weather-forecast"

_YAD_DISPLAY_COMMAND_="""exec yad \
--posx=$posx \
--posy=20 --undecorated --no-buttons \
--close-on-unfocus --fixed \
--text=\"$(cat $weather_forecast_tmp_file)\""""

dsApiKey = ""
constants = dict()
location = dict()

def Main():
    if IsInternetConnected():
        Setup()
        HandleBlockButton()
        print(GetStatusBarMessage())
    else:
        print(str("--\u2109  --"))


def IsInternetConnected():
    result = False

    output = subprocess.run(["ping", "-c", "1", "1.1.1.1"],
                            timeout=2.0,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            encoding="utf-8").stderr

    result = ("network is unreachable" not in output.lower())

    return result


def Setup():
    global dsApiKey
    global constants
    global location

    with open(str("%s/bin/i3blocks/block-constants.json" % getenv("HOME"))) as j:
        constants = json.load(j)
    
    config = configparser.ConfigParser()
    config.read("%s/.config/my-configs/api_keys.ini" % getenv("HOME"))

    # api keys
    dsApiKey = config["weather"]["DARKSKY_API_KEY"]

    # Get the current location of this computer
    # FIXME how to get the location of the system without contacting the internet?
    locrequest = requests.get("https://ipinfo.io").json()
    location = {
        "lat": float(locrequest["loc"].split(',')[0]),
        "lon": float(locrequest["loc"].split(',')[1])
    }


def HandleBlockButton():
    global location

    button = getenv("BLOCK_BUTTON")
    if not button:
        return
    elif button == "1": # Left click
        message = GetMultiHourForecasts(3) 
    elif button == "3": # Right click
        message = GetMultiDayForecasts(5)
    else:               # unhandled interaction
        return

    # Need to write message to file the cat the file because
    # i3-msg doesn't like new lines in arguments
    with open(_WEATHER_FORECAST_TMP_FILE_,'w') as w:
        w.write(message)
    
    runargs = ['i3-msg','-q',Template(_YAD_DISPLAY_COMMAND_).safe_substitute(dict(
        weather_forecast_tmp_file=_WEATHER_FORECAST_TMP_FILE_,
        posx=int(getenv("BLOCK_X")) - 200
    ))]

    subprocess.run(runargs)

def GetMultiHourForecasts(intervalHours):
    pass
    weather = GetWeatherFromSource("multihour-forecasts")["hourly"]

    message = "%s\n\n" % weather["summary"]
    for h in range(24):
        if (h + 1) % intervalHours == 0:
            message += "%s\n" % GetSingleHourForecast(weather["data"][h])

    return message


def GetSingleHourForecast(hourjson):

    forecastParams = {
        "time": GetForecastTimeHeader(hourjson["time"], _DATE_STR_FORMAT_WITH_TIME_),
        "condition": hourjson["summary"],
        "temp": "%s\u2109 " % int(hourjson["temperature"]),
        "precip": int(float(hourjson["precipProbability"]) * 100),
        "wind": hourjson["windSpeed"],
        "windg": hourjson["windGust"]
    }

    if HasSignificatApparentTemperatureDifference(hourjson, ["temperature", "apparentTemperature"]):
        forecastParams["temp"] = "%s\u2109 (%s\u2109 )" % (int(hourjson["temperature"]),
                                                            int(hourjson["apparentTemperature"]))

    result = Template(_HOUR_FORECAST_TEMPLATE_).safe_substitute(forecastParams)
    
    return result


def GetMultiDayForecasts(numOfDays):
    weather = GetWeatherFromSource("multiday-forecasts")["daily"]

    message = "%s\n\n" % weather["summary"]
    for d in range(numOfDays):
        message += "%s\n" % GetSingleDayForecast(weather["data"][d])

    return message


def GetSingleDayForecast(dayjson):
    
    forecastParams = {
        "date": GetForecastTimeHeader(dayjson["time"], _DATE_STR_FORMAT_),
        "condition": dayjson["summary"],
        "temp_l": int(dayjson["temperatureLow"]),
        "temp_al": int(dayjson["apparentTemperatureLow"]),
        "temp_h": int(dayjson["temperatureHigh"]),
        "temp_ah": int(dayjson["apparentTemperatureHigh"]),
        "precip": int(float(dayjson["precipProbability"]) * 100),
        "wind": dayjson["windSpeed"],
        "windg": dayjson["windGust"]
    }

    result = Template(_DAY_FORECAST_TEMPLATE_).safe_substitute(forecastParams)
    
    return result


def GetForecastTimeHeader(epochstr, ctimefmt):
    datestr = datetime.datetime.fromtimestamp(int(epochstr)).strftime(ctimefmt)
    result = "***** %s *****" % datestr

    return result


def GetStatusBarMessage():
    global location
    global dsApiKeys
    result = ""

    weather = GetWeatherFromSource("current-conditions")["currently"]

    if HasSignificatApparentTemperatureDifference(weather, ["temperature","apparentTemperature"]):
        result = "%s\u2109 (%s\u2109 ) %s" % (int(weather["temperature"]),
                                                int(weather["apparentTemperature"]),
                                                weather["summary"])
    else:
        result = "%s\u2109  %s" % (int(weather["temperature"]),
                                    weather["summary"])

    return result


def GetWeatherFromSource(reqTypeStr):
    reqParams = GetDarkSkyRequestParameters(reqTypeStr)
    requrl = Template(_DARKSKY_API_ADDRESS_).safe_substitute(reqParams)
    result = requests.get(requrl).json()

    return result


def GetDarkSkyRequestParameters(reqTypeStr):
    result = {
        "apikey": dsApiKey,
        "lat": location["lat"],
        "lon": location["lon"]
    }

    excludeItems = ["flags","minutely"]

    if reqTypeStr == "current-conditions":
        reqExcludeItems = ["hourly","daily"]
    elif reqTypeStr == "multiday-forecasts":
        reqExcludeItems = ["currently", "hourly"]
    elif reqTypeStr == "multihour-forecasts":
        reqExcludeItems = ["currently", "daily"]
    else:
        reqExcludeItems = []

    excludeItems.extend(reqExcludeItems)

    result["exclude_blocks"] = ",".join(excludeItems)

    return result


def HasSignificatApparentTemperatureDifference(weatherjson, targetKeys):
    temp = weatherjson[targetKeys[0]]
    appTemp = weatherjson[targetKeys[1]]

    result = (abs(temp - appTemp) > _TEMP_APPARENT_TEMP_SIGNIFICANCE_DIFF_)

    return result


if __name__ == "__main__":
    Main()
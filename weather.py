#!/usr/bin/env python3


import configparser
import datetime
import dpath.util
import json
from os import getenv
import pyowm
import requests
from string import Template
import subprocess

_DARKSKY_API_ADDRESS_ = "https://api.darksky.net/forecast/$apikey/$lat,$lon?units=us&exclude=$exclude_blocks"

_DATE_STR_FORMAT_ = '%a %b %d, %Y'
_DATE_STR_FORMAT_WITH_TIME_ = '%l:%M %p %a %b %d, %Y'

_DAY_FORECAST_SCHEMA_ = {
    "temp":"Temperature/$minmax/Value",
    "tempf":"RealFeelTemperature/$minmax/Value",
    "conditioni":"$daypart/IconPhrase",
    "conditions":"$daypart/ShortPhrase",
    "precip":"$daypart/PrecipitationProbability",
    "wind":"$daypart/Wind/Speed/Value",
    "windg":"$daypart/WindGust/Speed/Value"
}

# _DAY_FORECAST_TEMPLATE_ = """
# $daypart $temp\u2109 ($tempf\u2109 )
# $conditioni - $conditions
# Precip: ${precip}%
# Wind: $wind ($windg) mph
# """

_DAY_FORECAST_TEMPLATE_="""
$date
$condition
$temp_l\u2109 ($temp_al\u2109 ) - $temp_h\u2109 ($temp_ah\u2109 )
Precip: ${precip}%
Wind: $wind ($windg) mph
"""

_HOURE_FORECAST_TEMPLATE = """
$time
$temp\u2109  $conditioni - $conditions
Wind: $wind mph
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


accuApiKey = ""
dsApiKey = ""
constants = dict()
location = dict()
owmApiKey = ""

def Main():
    if IsInternetConnected():
        Setup()
        #GetMultiDayForecasts(5)
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
    global accuApiKey
    global dsApiKey
    global constants
    global location
    global owmApiKey

    with open(str("%s/bin/i3blocks/block-constants.json" % getenv("HOME"))) as j:
        constants = json.load(j)
    
    config = configparser.ConfigParser()
    config.read("%s/.config/my-configs/api_keys.ini" % getenv("HOME"))

    # api keys
    accuApiKey = config["weather"]["ACCUWEATHER_API_KEY"]
    owmApiKey = config["weather"]["OWM_API_KEY"]
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
        message = GetOneDayDetailedForecast() 
    elif button == "3": # Right click
        message = GetMultiDayForecasts(5)
    else:               # unhandled interaction
        return

    with open(_WEATHER_FORECAST_TMP_FILE_,'w') as w:
        w.write(message)
    
    runargs = ['i3-msg','-q',Template(_YAD_DISPLAY_COMMAND_).safe_substitute(dict(
        weather_forecast_tmp_file=_WEATHER_FORECAST_TMP_FILE_,
        posx=getenv("BLOCK_X")
    ))]

    subprocess.run(runargs)

def GetOneDayDetailedForecast():
    global location
    global owmApiKey
    result = ""

    owm = pyowm.OWM(owmApiKey)
    weathers = owm.three_hours_forecast_at_coords(location["lat"], location["lon"]).get_forecast().get_weathers()
    
    for w in range(8):
        aWeather = weathers[w]
        weatherparts = {
            "time": GetForecastTimeHeader(str(aWeather.get_reference_time()), _DATE_STR_FORMAT_WITH_TIME_),
            "temp": int(aWeather.get_temperature(_TEMP_UNIT_)["temp"]),
            "conditioni": aWeather.get_status(),
            "conditions": aWeather.get_detailed_status(),
            "precip": int(GetOwmPrecipPercentage([aWeather.get_rain(), aWeather.get_snow()])),
            "wind": int(aWeather.get_wind("miles_hour")["speed"])
        }

        result += Template(_HOURE_FORECAST_TEMPLATE).safe_substitute(weatherparts)

    return result

def GetForecastTimeHeader(epochstr, ctimefmt):
    datestr = datetime.datetime.fromtimestamp(int(epochstr)).strftime(ctimefmt)
    result = "***** %s *****" % datestr

    return result

def GetOwmPrecipPercentage(precipDicts):
    result = 0
    for pDict in precipDicts:
        if pDict and float(pDict["3h"]) > result:
            result = pDict["3h"]

    return result * 100


def GetMultiDayForecasts(numOfDays):
    weather = GetWeatherRequestResponse("multiday-forecasts")["daily"]

    message = "%s\n\n" % weather["summary"]
    for d in range(numOfDays):
        message += "%s\n" % GetDayForecast(weather["data"][d])

    return message


def GetDayForecast(dayjson):

    result = "%s\n" % GetForecastTimeHeader(dayjson["time"], _DATE_STR_FORMAT_)
    
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

def GetStatusBarMessage():
    global location
    global dsApiKeys
    result = ""

    weather = GetWeatherRequestResponse("current-conditions")["currently"]

    if HasSignificatApparentTemperatureDifference(weather, ["temperature","apparentTemperature"]):
        result = "%s\u2109 (%s\u2109 ) %s" % (int(weather["temperature"]),
                                                int(weather["apparentTemperature"]),
                                                weather["summary"])
    else:
        result = "%s\u2109  %s" % (int(weather["temperature"]),
                                    weather["summary"])

    return result

def GetWeatherRequestResponse(reqTypeStr):
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
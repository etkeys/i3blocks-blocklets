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

_DATE_STR_FORMAT_ = '%a %b %d, %Y'

_DAY_FORECAST_SCHEMA_ = {
    "temp":"Temperature/$minmax/Value",
    "tempf":"RealFeelTemperature/$minmax/Value",
    "conditioni":"$daypart/IconPhrase",
    "conditions":"$daypart/ShortPhrase",
    "precip":"$daypart/PrecipitationProbability",
    "wind":"$daypart/Wind/Speed/Value",
    "windg":"$daypart/WindGust/Speed/Value"
}

_DAY_FORECAST_TEMPLATE_ = """
$daypart $temp\u2109 ($tempf\u2109 )
$conditioni - $conditions
Precip: ${precip}%
Wind: $wind ($windg) mph
"""

_TEMP_UNIT_ = 'fahrenheit'

_WEATHER_FORECAST_TMP_FILE_="/tmp/weather-forecast"

_YAD_DISPLAY_COMMAND_="""exec yad \
--posx=$posx \
--posy=20 --undecorated --no-buttons \
--close-on-unfocus --fixed \
--text=\"$(cat $weather_forecast_tmp_file)\""""


accuApiKey = ""
constants = dict()
location = dict()
owmApiKey = ""

def Main():
    if IsInternetConnected():
        Setup()
        HandleBlockButton()
        statusMessage = GetStatusBarMessage()
        print(statusMessage)
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

    accuLocInfo = requests.get("http://dataservice.accuweather.com/locations/v1/cities/geoposition/search?apikey=%s&q=%s,%s" %
                                (accuApiKey,location["lat"], location["lon"])).json()
    locKey = accuLocInfo["Key"]

    day1forecast = requests.get("http://dataservice.accuweather.com/forecasts/v1/daily/1day/%s?apikey=%s&details=true" %
                                (locKey, accuApiKey)).json()["DailyForecasts"][0]
    
    # with open('/tmp/weather-sample.out') as w:
    #     day1forecast = json.load(w)

    message = GetDayForecast(day1forecast)
    with open(_WEATHER_FORECAST_TMP_FILE_,'w') as w:
        w.write(message)
    
    runargs = ['i3-msg','-q',Template(_YAD_DISPLAY_COMMAND_).safe_substitute(dict(
        weather_forecast_tmp_file=_WEATHER_FORECAST_TMP_FILE_,
        posx=getenv("BLOCK_X")
    ))]
    #print(runargs)

    subprocess.run(runargs)


def GetDayForecast(dayjson):
    dayparts = ["Day", "Night"]

    # Get the date specified in dayjson and convert it to a
    # pretty date
    epoch=int(dayjson["EpochDate"])
    datestr=datetime.date.fromtimestamp(epoch).strftime(_DATE_STR_FORMAT_)
    result = "*** %s ***" % datestr


    # For both Day and Night, get the parameterized values
    # from the dayjson that will be inserted into forecast
    # result message
    for daypart in dayparts:
        weatherparts = {"daypart": daypart}
        dayvariants = GetDayVariantValues(daypart)

        for name, path in _DAY_FORECAST_SCHEMA_.items():
            path = Template(path).safe_substitute(dayvariants)
            weatherparts[name] = dpath.util.get(dayjson,path)
        
        result += Template(_DAY_FORECAST_TEMPLATE_).safe_substitute(weatherparts)

    return result


# Certain values, like temperature, are not kept in the
# "part of day" value like much of the other pieces of
# weather information. Because of this, we have to have
# parameter replacements values 
def GetDayVariantValues(daypart):
    result = dict()
    if daypart == "Day":
        result["minmax"] = "Maximum"
            
    elif daypart == "Night":
        result["minmax"] = "Minimum"
    
    result["daypart"] = daypart
    return result


def GetStatusBarMessage():
    global location
    global owmApiKey
    result = ""

    owm = pyowm.OWM(owmApiKey)
    weather = owm.weather_at_coords(location["lat"], location["lon"]).get_weather();

    result = str("%s\u2109  %s" % (int(weather.get_temperature(_TEMP_UNIT_)["temp"]),
                                    weather.get_status()))
    
    return result


if __name__ == "__main__":
    Main()
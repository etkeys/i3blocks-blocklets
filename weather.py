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

_DAY_FORECAST_TEMPLATE_ = """
$daypart $temp\u2109 ($tempf\u2109 )
$conditioni - $conditions
Precip: ${precip}%
Wind: $wind ($windg) mph
"""

_HOURE_FORECAST_TEMPLATE = """
$time
$temp\u2109  $conditioni - $conditions
Wind: $wind mph
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
        #GetOneDayDetailedForecast()
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
    accuLocInfo = requests.get("http://dataservice.accuweather.com/locations/v1/cities/geoposition/search?apikey=%s&q=%s,%s" %
                                (accuApiKey,location["lat"], location["lon"])).json()
    locKey = accuLocInfo["Key"]

    dayforecasts = requests.get("http://dataservice.accuweather.com/forecasts/v1/daily/5day/%s?apikey=%s&details=true" %
                            (locKey, accuApiKey)).json()["DailyForecasts"]

    # print(dayforecast)

    # with open('/tmp/weather-sample.out') as w:
    #     dayforecasts = json.load(w)["DailyForecasts"]

    message = ""
    for d in range(numOfDays):
        message += "%s\n" % GetDayForecast(dayforecasts[d])

    return message


def GetDayForecast(dayjson):
    dayparts = ["Day", "Night"]

    result = "%s\n" % GetForecastTimeHeader(dayjson["EpochDate"], _DATE_STR_FORMAT_)


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

    #print(weather.to_JSON())

    result = str("%s\u2109  %s" % (int(weather.get_temperature(_TEMP_UNIT_)["temp"]),
                                    weather.get_detailed_status()))
    
    return result


if __name__ == "__main__":
    Main()
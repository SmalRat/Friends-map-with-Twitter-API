"""
A module of web application, which creates a map with markers indicating locations of accounts\
 followed by given username.
"""
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request
import folium
import requests
import os
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderUnavailable

app = Flask(__name__)
load_dotenv()
token = os.environ.get("BEARER_TOKEN")


def map_creation(friends):
    """
    Creates a map with markers. Each marker corresponds to one friend from 'friends' list.
    """

    friends_map = folium.Map()
    fg = folium.FeatureGroup(name="Friends locations")
    html = """<body>
              <h4>Friend's username:</h4>
              <h3>{}</h3>
              </body>
           """

    for friend in friends:
        html_format = html.format(friend[1])
        iframe = folium.IFrame(html=html_format, width=200, height=100)
        fg.add_child(folium.Marker(location=[friend[0][0], friend[0][1]],
                                   popup=folium.Popup(iframe),
                                   icon=folium.Icon(color="blue")))
    friends_map.add_child(fg)
    return friends_map.get_root().render()


def queries(url, querystring):
    """
    Sends a queries.
    """
    bearer = 'Bearer ' + token
    headers = {"Authorization": bearer}

    response = requests.request("GET", url, headers=headers, params=querystring)

    return response.json()


def memoize_and_write(func, places_dict):
    """
    Decorator for memoization
    """

    def wrapper(place):
        """
        Wrapper. Organises the cache usage and its creation.
        """
        try:
            place = str(place)
            original_place = place

            while True:
                if place not in places_dict.keys() and place != "nan":
                    coordinates = func(place)

                    if coordinates:
                        coordinates = tuple([coordinates.point[0], coordinates.point[1]])
                        places_dict[original_place] = coordinates
                        return coordinates
                    else:
                        if len(place.split(",")) > 1:
                            place = crop_address(place)
                        else:
                            places_dict[original_place] = coordinates
                            return coordinates
                elif place == "nan":
                    return None
                else:
                    raw_coordinates = places_dict[place]
                    if isinstance(raw_coordinates, tuple):
                        return raw_coordinates
                    try:
                        try:
                            coordinates = tuple(
                                [float(i) for i in tuple(raw_coordinates[1:\
                                len(raw_coordinates) - 1].split(", "))])
                            return coordinates
                        except ValueError:
                            return None
                    except:
                        return None
        except GeocoderUnavailable:
            print("GeocoderUnavailable error for this location:" + place + ". Proceeding...")
            return None

    return wrapper


def crop_address(place):
    """
    Crops address and returns new variant
    >>> crop_address("Jo's Cafe, San Marcos, Texas, USA")
    ' San Marcos, Texas, USA'
    >>> crop_address("San Marcos, Texas, USA")
    ' Texas, USA'
    >>> crop_address(" Texas, USA")
    ' USA'
    """

    place = place.split(",")
    place = ",".join(place[1:])

    return place


@app.route("/")
def index():
    """
    Starting page.
    """
    return render_template("index.html")


@app.route("/generate_map", methods=["POST"])
def map_generation():
    """
    Page with a friends map.
    """
    geolocator = Nominatim(user_agent="Friends map")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=0.3, max_retries=2, \
                          swallow_exceptions=True, \
                          return_value_on_exception=None, error_wait_seconds=2)
    geo = memoize_and_write(geocode, {})

    name = request.form.get("Account name")

    if not name:
        return redirect("/no_username_error")

    url = "https://api.twitter.com/2/users/by/username/" + name
    res = queries(url, None)

    if 'data' not in res:
        return redirect("/does_not_exist_error")
    user_id = res["data"]["id"]

    url = "https://api.twitter.com/2/users/" + str(user_id) + "/following"
    querystring = {"user.fields": "location"}
    res = queries(url, querystring)

    friends_list = []
    for friend in res['data']:
        try:
            coordinates = geo(friend['location'])
            if coordinates:
                friends_list.append(tuple([coordinates, friend['username']]))
        except KeyError:
            pass

    return map_creation(friends_list)


@app.route("/no_username_error")
def no_username_error():
    """
    A page for no username error.
    """
    return render_template("failure_no_username.html")


@app.route("/does_not_exist_error")
def does_not_exist_error():
    """
    A page for a case when the username doesn't exist.
    """
    return render_template("failure_does_not_exist.html")


if __name__ == "__main__":
    app.run(debug=False, host='127.0.0.1', port=8080)

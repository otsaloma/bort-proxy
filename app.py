# -*- coding: utf-8 -*-

# Copyright (c) 2016 Osmo Salomaa
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import base64
import contextlib
import flask
import imghdr
import io
import json
import os
import pickle
import PIL.Image
import random
import re
import redis
import requests
import urllib.parse
import xml.etree.ElementTree as ET

FALLBACK_PNG = open("fallback.png", "rb").read()
app = flask.Flask(__name__)
blacklist = set()

if "REDISCLOUD_URL" in os.environ:
    # Production config values are set in the dashboard.
    # See 'heroku addons:open rediscloud'.
    cache = redis.from_url(os.environ["REDISCLOUD_URL"])
else:
    cache = redis.from_url("redis://localhost")
    cache.config_set("maxmemory", "30mb")
    cache.config_set("maxmemory-policy", "allkeys-lru")
    if app.debug: cache.flushdb()

# Cache HTTP connections for better performance.
# https://urllib3.readthedocs.io/en/latest/advanced-usage.html#customizing-pool-behavior
adapter = requests.adapters.HTTPAdapter(pool_connections=10,
                                        pool_maxsize=100,
                                        max_retries=0,
                                        pool_block=False)

rs = requests.Session()
rs.mount("http://", adapter)
rs.mount("https://", adapter)


@app.route("/facebook-icon")
def facebook_icon():
    """Return a downscaled Facebook profile image."""
    user = flask.request.args["user"]
    size = int(flask.request.args["size"])
    format = flask.request.args.get("format", "png")
    key = "facebook-icon:{}:{:d}".format(user, size)
    if cache.exists(key):
        print("Found in cache: {}".format(key))
        image, ttl = get_from_cache(key)
        return make_response(image, format, ttl)
    url = "https://graph.facebook.com/{user}/picture?type=large"
    url = url.format(user=urllib.parse.quote(user))
    try:
        print("Requesting {}".format(url))
        image = request_image(url, max_size=5)
        image = resize_image(image, size)
        if imghdr.what(None, image) != "png":
            raise ValueError("Non-PNG data received")
        cache.set(key, image, ex=7*86400)
        return make_response(image, format)
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        cache.set(key, FALLBACK_PNG, ex=43200)
        return make_response(FALLBACK_PNG, format, 43200)

@app.route("/favicon")
def favicon():
    """Return a 16x16 favicon for website."""
    domain = flask.request.args["url"]
    domain = re.sub("/.*$", "", re.sub("^.*?://", "", domain))
    format = flask.request.args.get("format", "png")
    key = "favicon:{}".format(domain)
    if cache.exists(key):
        print("Found in cache: {}".format(key))
        image, ttl = get_from_cache(key)
        return make_response(image, format, ttl)
    url = "https://www.google.com/s2/favicons?domain={domain}"
    url = url.format(domain=urllib.parse.quote(domain))
    try:
        print("Requesting {}".format(url))
        image = request_image(url, max_size=1)
        if imghdr.what(None, image) != "png":
            raise ValueError("Non-PNG data received")
        cache.set(key, image, ex=7*86400)
        return make_response(image, format)
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        cache.set(key, FALLBACK_PNG, ex=43200)
        return make_response(FALLBACK_PNG, format, 43200)

def get_cache_control(max_age):
    """Return a Cache-Control header for `max_age`."""
    return "public, max-age={:d}".format(max_age)

def get_from_cache(key):
    """Return value, ttl for `key` from cache."""
    return cache.get(key), cache.ttl(key)

@app.route("/google-search-suggestions")
def google_search_suggestions():
    """Return a JSON array of Google search suggestions for query."""
    query = flask.request.args["query"]
    lang = flask.request.args.get("lang", "en")
    key = "google-search-suggestions:{}:{}".format(query, lang)
    if cache.exists(key):
        print("Found in cache: {}".format(key))
        data, ttl = get_from_cache(key)
        return make_response(pickle.loads(data), "json", ttl)
    url = "https://suggestqueries.google.com/complete/search?output=toolbar&q={query}&hl={lang}"
    url = url.format(query=urllib.parse.quote_plus(query), lang=lang)
    try:
        print("Requesting {}".format(url))
        response = rs.get(url, timeout=5)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        suggestions = [x.get("data") for x in root.iter("suggestion")]
        cache.set(key, pickle.dumps(suggestions), ex=3600)
        return make_response(suggestions, "json")
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        cache.set(key, pickle.dumps([]), ex=3600)
        return make_response([], "json", 3600)

@app.route("/icon")
def icon():
    """Return favicon or apple-touch-icon for website."""
    domain = flask.request.args["url"]
    domain = re.sub("/.*$", "", re.sub("^.*?://", "", domain))
    size = int(flask.request.args["size"])
    format = flask.request.args.get("format", "png")
    key = "icon:{}:{:d}".format(domain, size)
    if cache.exists(key):
        print("Found in cache: {}".format(key))
        image, ttl = get_from_cache(key)
        return make_response(image, format, ttl)
    url = "https://icons.better-idea.org/icon?url={domain}&size={size:d}"
    url = url.format(domain=urllib.parse.quote(domain), size=size)
    try:
        print("Requesting {}".format(url))
        image = request_image(url, max_size=1)
        image = resize_image(image, size)
        if imghdr.what(None, image) != "png":
            raise ValueError("Non-PNG data received")
        cache.set(key, image, ex=7*86400)
        return make_response(image, format)
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        cache.set(key, FALLBACK_PNG, ex=43200)
        return make_response(FALLBACK_PNG, format, 43200)

@app.route("/image")
def image():
    """Return a downscaled image read from URL."""
    url = flask.request.args["url"]
    size = int(flask.request.args["size"])
    format = flask.request.args.get("format", "png")
    key = "image:{}:{:d}".format(url, size)
    if cache.exists(key):
        print("Found in cache: {}".format(key))
        image, ttl = get_from_cache(key)
        return make_response(image, format, ttl)
    try:
        print("Requesting {}".format(url))
        image = request_image(url, max_size=1)
        image = resize_image(image, size)
        if imghdr.what(None, image) != "png":
            raise ValueError("Non-PNG data received")
        cache.set(key, image, ex=7*86400)
        return make_response(image, format)
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        cache.set(key, FALLBACK_PNG, ex=43200)
        return make_response(FALLBACK_PNG, format, 43200)

def make_response(data, format, max_age=None):
    """Return response 200 for `data` as `format`."""
    if format == "base64":
        text = base64.b64encode(data)
        max_age = max_age or random.randint(1,3) * 86400
        return flask.Response(text, 200, {
            "Content-Type": "text/plain",
            "Content-Encoding": "UTF-8",
            "Content-Length": str(len(text)),
            "Cache-Control": get_cache_control(max_age),
        })
    if format == "json":
        text = json.dumps(data, ensure_ascii=False)
        max_age = max_age or 3600
        return flask.Response(text, 200, {
            "Content-Type": "application/json",
            "Content-Encoding": "UTF-8",
            "Content-Length": str(len(text)),
            "Cache-Control": get_cache_control(max_age),
        })
    if format == "png":
        max_age = max_age or random.randint(1,3) * 86400
        return flask.Response(data, 200, {
            "Content-Type": "image/png",
            "Content-Length": str(len(data)),
            "Cache-Control": get_cache_control(max_age),
        })

def request_image(url, max_size=1, timeout=10):
    """Request and return image at `url` at most `max_size` MB."""
    # Avoid getting caught reading insanely large files.
    # http://docs.python-requests.org/en/master/user/advanced/#body-content-workflow
    if url in blacklist:
        raise ValueError("URL blacklisted")
    max_size = max_size * 1024 * 1024
    with contextlib.closing(requests.get(
            url, timeout=timeout, stream=True)) as response:
        response.raise_for_status()
        if ("content-length" in response.headers
            and response.headers["content-length"].isdigit()
            and int(response.headers["content-length"]) > max_size):
            raise ValueError("Too large")
        image = response.raw.read(max_size+1, decode_content=True)
        if len(image) <= max_size: return image
        blacklist.add(url)
        raise ValueError("Too large")

def resize_image(image, size, threshold=2):
    """Resize `image` to `size` and return PNG bytes."""
    pi = PIL.Image.open(io.BytesIO(image))
    if not pi.mode in ("RGB", "RGBA"):
        pi = pi.convert("RGBA")
    pi.thumbnail((size, size), PIL.Image.BICUBIC)
    if pi.width != pi.height:
        # Add transparent margins to make a square image.
        bg = PIL.Image.new("RGBA", (size, size), (255, 255, 255, 0))
        bg.paste(pi, ((size - pi.width) // 2, (size - pi.height) // 2))
        pi = bg
    out = io.BytesIO()
    pi.save(out, "PNG")
    return out.getvalue()

@app.route("/twitter-icon")
def twitter_icon():
    """Return a downscaled Twitter profile image."""
    user = flask.request.args["user"]
    size = int(flask.request.args["size"])
    format = flask.request.args.get("format", "png")
    key = "twitter-icon:{}:{:d}".format(user, size)
    if cache.exists(key):
        print("Found in cache: {}".format(key))
        image, ttl = get_from_cache(key)
        return make_response(image, format, ttl)
    url = "https://twitter.com/{user}/profile_image?size=original"
    url = url.format(user=urllib.parse.quote(user))
    try:
        print("Requesting {}".format(url))
        image = request_image(url, max_size=5)
        image = resize_image(image, size)
        if imghdr.what(None, image) != "png":
            raise ValueError("Non-PNG data received")
        cache.set(key, image, ex=7*86400)
        return make_response(image, format)
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        cache.set(key, FALLBACK_PNG, ex=43200)
        return make_response(FALLBACK_PNG, format, 43200)

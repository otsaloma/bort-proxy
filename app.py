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
import flask
import io
import json
import os
import PIL.Image
import random
import re
import redis
import requests
import urllib.parse
import xml.etree.ElementTree as ET

app = flask.Flask(__name__)

if "REDISCLOUD_URL" in os.environ:
    # Production config values are set in the dashboard.
    # See 'heroku addons:open rediscloud'.
    cache = redis.from_url(os.environ["REDISCLOUD_URL"])
else:
    cache = redis.from_url("redis://localhost")
    cache.config_set("maxmemory", "30mb")
    cache.config_set("maxmemory-policy", "allkeys-lru")
    if app.debug: cache.flushdb()


@app.route("/favicon")
def favicon():
    """Return a 16x16 favicon for website."""
    domain = flask.request.args["url"]
    domain = re.sub("/.*$", "", re.sub("^.*://", "", domain))
    format = flask.request.args.get("format", "png")
    key = "favicon:{}".format(domain)
    image = cache.get(key)
    if image is not None:
        print("Found in cache: {}".format(key))
        return make_image_response(image, format)
    url = "https://www.google.com/s2/favicons?domain={domain}"
    url = url.format(domain=urllib.parse.quote(domain))
    print("Requesting {}".format(url))
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    cache.set(key, response.content)
    return make_image_response(response.content, format)

def get_image_cache_control():
    """Return a Cache-Control header for serving images."""
    return "public, max-age={:d}".format(random.randint(1, 3) * 86400)

@app.route("/google-search-suggestions")
def google_search_suggestions():
    """Return a JSON array of Google search suggestions for query."""
    query = flask.request.args["query"]
    lang = flask.request.args.get("lang", "en")
    key = "google-search-suggestions:{}:{}".format(query, lang)
    suggestions = cache.get(key)
    if suggestions is not None:
        print("Found in cache: {}".format(key))
        return make_json_response(suggestions)
    url = "https://suggestqueries.google.com/complete/search?output=toolbar&q={query}&hl={lang}"
    url = url.format(query=urllib.parse.quote_plus(query), lang=lang)
    print("Requesting {}".format(url))
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    suggestions = [x.get("data") for x in root.iter("suggestion")]
    return make_json_response(suggestions)

@app.route("/icon")
def icon():
    """Return favicon or apple-touch-icon for website."""
    domain = flask.request.args["url"]
    domain = re.sub("/.*$", "", re.sub("^.*://", "", domain))
    size = int(flask.request.args["size"])
    format = flask.request.args.get("format", "png")
    key = "icon:{}:{:d}".format(domain, size)
    image = cache.get(key)
    if image is not None:
        print("Found in cache: {}".format(key))
        return make_image_response(image, format)
    url = "https://icons.better-idea.org/icon?url={domain}&size={size:d}"
    url = url.format(domain=urllib.parse.quote(domain), size=size)
    print("Requesting {}".format(url))
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    # XXX: Inspect with imghdr and return in original format?
    image = resize_image(response.content, size)
    cache.set(key, image)
    return make_image_response(image, format)

@app.route("/image")
def image():
    """Return a downscaled image read from URL."""
    url = flask.request.args["url"]
    size = int(flask.request.args["size"])
    format = flask.request.args.get("format", "png")
    key = "image:{}:{:d}".format(url, size)
    image = cache.get(key)
    if image is not None:
        print("Found in cache: {}".format(key))
        return make_image_response(image, format)
    print("Requesting {}".format(url))
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    image = resize_image(response.content, size)
    cache.set(key, image)
    return make_image_response(image, format)

def make_image_response(image, format):
    """Return response for `image` as `format`."""
    return {
        "base64": make_image_response_base64,
        "png": make_image_response_png,
    }[format](image)

def make_image_response_base64(image):
    """Return response for `image` as a base64 string."""
    text = base64.b64encode(image)
    return flask.Response(text, 200, {
        "Content-Type": "text/plain",
        "Content-Encoding": "UTF-8",
        "Content-Length": str(len(text)),
        "Cache-Control": get_image_cache_control(),
    })

def make_image_response_png(image):
    """Return response for `image` as a PNG image."""
    return flask.Response(image, 200, {
        "Content-Type": "image/png",
        "Content-Length": str(len(image)),
        "Cache-Control": get_image_cache_control(),
    })

def make_json_response(obj):
    """Return response for `obj` as a JSON string."""
    text = json.dumps(obj, ensure_ascii=False)
    return flask.Response(text, 200, {
        "Content-Type": "application/json",
        "Content-Encoding": "UTF-8",
        "Content-Length": str(len(text)),
        "Cache-Control": "public, max-age=3600",
    })

def resize_image(image, size):
    """Resize `image` to `size` and return PNG bytes."""
    pi = PIL.Image.open(io.BytesIO(image))
    pi.thumbnail((size, size), PIL.Image.LANCZOS)
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
    image = cache.get(key)
    if image is not None:
        print("Found in cache: {}".format(key))
        return make_image_response(image, format)
    url = "https://twitter.com/{user}/profile_image?size=original"
    url = url.format(user=urllib.parse.quote(user))
    print("Requesting {}".format(url))
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    image = resize_image(response.content, size)
    cache.set(key, image)
    return make_image_response(image, format)

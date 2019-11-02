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
import bs4
import contextlib
import flask
import functools
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
import traceback
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

FALLBACK_PNG = open("letter-icons/x.png", "rb").read()

LINK_REL_PATTERNS = [
    re.compile("^apple-touch-icon$"),
    re.compile("^apple-touch-icon-precomposed$"),
    re.compile("^icon$"),
    re.compile("^shortcut icon$"),
]

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
        cache.set(key, image, ex=rex(3, 5))
        return make_response(image, format)
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        image = resize_image(FALLBACK_PNG, size)
        cache.set(key, image, ex=7200)
        return make_response(image, format, 7200)

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
        cache.set(key, image, ex=rex(3, 5))
        return make_response(image, format)
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        image = resize_image(FALLBACK_PNG, 16)
        cache.set(key, image, ex=7200)
        return make_response(image, format, 7200)

def find_icons(url):
    """Yield icon entries specified in the HTML HEAD of `url`."""
    url, page = get_page(url)
    soup = bs4.BeautifulSoup(page, "html.parser")
    for pattern in LINK_REL_PATTERNS:
        for tag in soup.find_all("link", dict(rel=pattern)):
            href = urllib.parse.urljoin(url, tag.attrs["href"])
            size = tag.attrs.get("sizes", "0x0")
            yield dict(url=href, size=int(size.split("x")[0]))
    # Fall back on looking for icons at the server root.
    join = lambda x: urllib.parse.urljoin(url, x)
    yield dict(url=join("/apple-touch-icon.png"), fallback=True)
    yield dict(url=join("/apple-touch-icon-precomposed.png"), fallback=True)

def get_cache_control(max_age):
    """Return a Cache-Control header for `max_age`."""
    return "public, max-age={:d}".format(max_age)

def get_from_cache(key):
    """Return value, ttl for `key` from cache."""
    return cache.get(key), cache.ttl(key)

def get_letter(url):
    """Return letter to represent `url`."""
    if "://" not in url:
        url = "http://{}".format(url)
    url = urllib.parse.urlparse(url).netloc
    url = url.split(".")
    url = url[-2] if len(url) > 1 else url[0]
    return url[0].lower() if url else "x"

@functools.lru_cache(256)
def get_letter_icon(letter):
    """Return letter icon PNG bytes for `url`."""
    fname = "letter-icons/{}.png".format(letter)
    if os.path.isfile(fname):
        with open(fname, "rb") as f:
            return f.read()
    name = unicodedata.name(letter)
    name = name.lower().replace(" ", "-")
    fname = "letter-icons/{}.png".format(name)
    if os.path.isfile(fname):
        with open(fname, "rb") as f:
            return f.read()
    return FALLBACK_PNG

def get_page(url, timeout=15):
    """Return evaluated `url`, HTML page as text."""
    if "://" in url:
        response = rs.get(url, timeout=timeout)
        response.raise_for_status()
        return response.url, response.text
    for scheme in ("https", "http"):
        with silent(Exception):
            return get_page("{}://{}".format(scheme, url))
    raise Exception("Failed to get page")

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
    """Return apple-touch-icon or favicon for website."""
    url = flask.request.args["url"]
    size = int(flask.request.args["size"])
    format = flask.request.args.get("format", "png")
    key = "icon:{}:{:d}".format(url, size)
    if cache.exists(key):
        print("Found in cache: {}".format(key))
        image, ttl = get_from_cache(key)
        return make_response(image, format, ttl)
    try:
        print("Parsing {}".format(url))
        icons = list(find_icons(url))
        icons.sort(key=lambda x: x.get("size", 0) or 1000)
    except Exception as error:
        print("Error parsing {}: {}".format(
            flask.request.full_path, str(error)))
        icons = []
    for icon in icons:
        # Ignore icons with a known size less than requested.
        icon.setdefault("size", 0)
        if 0 < icon["size"] < size: continue
        try:
            print("Requesting {}".format(icon["url"]))
            image = request_image(icon["url"])
            with PIL.Image.open(io.BytesIO(image)) as pi:
                if min(pi.width, pi.height) < size: continue
            image = resize_image(image, size)
            if imghdr.what(None, image) != "png":
                raise ValueError("Non-PNG data received")
            cache.set(key, image, ex=rex(3, 5))
            return make_response(image, format)
        except Exception as error:
            print("Error requesting {}: {}".format(
                icon["url"], str(error)))
    # Fall back on letter icons for domain.
    image = get_letter_icon(get_letter(url))
    image = resize_image(image, size)
    cache.set(key, image, ex=rex(3, 5))
    return make_response(image, format)

@app.route("/icons")
def icons():
    """Return JSON listing of icons for website."""
    url = flask.request.args["url"]
    key = "icons:{}".format(url)
    if cache.exists(key):
        print("Found in cache: {}".format(key))
        data, ttl = get_from_cache(key)
        return make_response(pickle.loads(data), "json", ttl)
    try:
        print("Parsing {}".format(url))
        icons = list(find_icons(url))
    except Exception as error:
        print("Error parsing {}: {}".format(
            flask.request.full_path, str(error)))
        icons = []
    for i in list(range(len(icons) - 1, -1, -1)):
        if icons[i].get("size", 1) < 1: del icons[i]["size"]
        if icons[i].get("fallback", False): del icons[i]
    data = dict(icons=icons)
    cache.set(key, pickle.dumps(data), ex=300)
    return make_response(data, "json", 300)

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
        cache.set(key, image, ex=rex(3, 5))
        return make_response(image, format)
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        image = resize_image(FALLBACK_PNG, size)
        cache.set(key, image, ex=7200)
        return make_response(image, format, 7200)

def make_response(data, format, max_age=None):
    """Return response 200 for `data` as `format`."""
    if format == "base64":
        text = base64.b64encode(data)
        max_age = max_age or random.randint(1, 3) * 86400
        return flask.Response(text, 200, {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
            "Content-Encoding": "UTF-8",
            "Content-Length": str(len(text)),
            "Cache-Control": get_cache_control(max_age),
        })
    if format == "json":
        text = json.dumps(data, ensure_ascii=False)
        max_age = max_age or 3600
        return flask.Response(text, 200, {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json",
            "Content-Encoding": "UTF-8",
            "Content-Length": str(len(text)),
            "Cache-Control": get_cache_control(max_age),
        })
    if format == "png":
        max_age = max_age or random.randint(1, 3) * 86400
        return flask.Response(data, 200, {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "image/png",
            "Content-Length": str(len(data)),
            "Cache-Control": get_cache_control(max_age),
        })

def request_image(url, max_size=1, timeout=15):
    """Request and return image at `url` at most `max_size` MB."""
    # Avoid getting caught reading insanely large files.
    # http://docs.python-requests.org/en/master/user/advanced/#body-content-workflow
    if url in blacklist:
        raise ValueError("URL blacklisted")
    max_size = max_size * 1024 * 1024
    with contextlib.closing(rs.get(
            url, timeout=timeout, stream=True)) as response:
        response.raise_for_status()
        if ("content-length" in response.headers and
            response.headers["content-length"].isdigit() and
            int(response.headers["content-length"]) > max_size):
            raise ValueError("Too large")
        image = response.raw.read(max_size+1, decode_content=True)
        if len(image) <= max_size: return image
        blacklist.add(url)
        raise ValueError("Too large")

def resize_image(image, size, threshold=2):
    """Resize `image` to `size` and return PNG bytes."""
    with PIL.Image.open(io.BytesIO(image)) as pi:
        if pi.mode not in ("RGB", "RGBA"):
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

def rex(a, b):
    """Return a random amount of seconds between a and b days."""
    return random.randint(int(a*86400), int(b*86400))

@contextlib.contextmanager
def silent(*exceptions, tb=False):
    """Try to execute body, ignoring `exceptions`."""
    try:
        yield
    except exceptions:
        if tb: traceback.print_exc()

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
        cache.set(key, image, ex=rex(3, 5))
        return make_response(image, format)
    except Exception as error:
        print("Error requesting {}: {}".format(
            flask.request.full_path, str(error)))
        image = resize_image(FALLBACK_PNG, size)
        cache.set(key, image, ex=7200)
        return make_response(image, format, 7200)

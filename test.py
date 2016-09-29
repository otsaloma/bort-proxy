#!/usr/bin/env python3

import requests
import sys

URL_PREFIX = sys.argv[1]

def test(path):
    url = URL_PREFIX + path
    print("{}: ".format(url), end="")
    response = requests.get(url, timeout=10)
    print(response.status_code)
    response.raise_for_status()

test("favicon?url=google.com")
test("favicon?url=google.com&format=base64")
test("favicon?url=google.com&format=png")

test("google-search-suggestions?query=helsinki")
test("google-search-suggestions?query=helsinki&lang=fi")

test("icon?url=github.com&size=96")
test("icon?url=github.com&size=96&format=base64")
test("icon?url=github.com&size=96&format=png")

test("image?url=https%3A%2F%2Fbort.io%2Fscreenshot.png&size=96")
test("image?url=https%3A%2F%2Fbort.io%2Fscreenshot.png&size=96&format=base64")
test("image?url=https%3A%2F%2Fbort.io%2Fscreenshot.png&size=96&format=png")

test("twitter-icon?user=apple&size=96")
test("twitter-icon?user=apple&size=96&format=base64")
test("twitter-icon?user=apple&size=96&format=png")

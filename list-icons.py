#!/usr/bin/env python3

import os

os.environ["FLASK_ENV"] = "development"

import app
import sys

for icon in app.find_icons(sys.argv[1]):
    print(icon)

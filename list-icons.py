#!/usr/bin/env python3

import sys
sys.argv.append("--debug")

import app

for icon in app.find_icons(sys.argv[1]):
    print(icon)

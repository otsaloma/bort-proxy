#!/usr/bin/env python3

import importlib
import os
import sys

path = os.path.join(os.path.dirname(__file__), "app.py")
loader = importlib.machinery.SourceFileLoader("app", path)
app = loader.load_module("app")

for icon in app.find_icons(sys.argv[1]):
    print(icon)

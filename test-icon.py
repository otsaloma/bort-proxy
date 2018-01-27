#!/usr/bin/env python3

import importlib
import os

path = os.path.join(os.path.dirname(__file__), "app.py")
loader = importlib.machinery.SourceFileLoader("app", path)
app = loader.load_module("app")

for icon in app.find_icons("github.com"):
    print(icon)

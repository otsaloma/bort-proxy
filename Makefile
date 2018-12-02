# -*- coding: utf-8-unix -*-

NAME = `basename $$PWD`

export FLASK_APP = app.py
export FLASK_DEBUG = 1

check:
	pyflakes app.py

clean:
	rm -rf __pycache__

run:
	flask run

.PHONY: check clean run

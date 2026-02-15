# -*- coding: utf-8-unix -*-

include .env
export

PYTHON := python3.13

check:
	flake8 app.py

clean:
	rm -rf __pycache__

run:
	flask --app=app.py run --debug

test:
	./test.py

test-production:
	HOST=https://bort-proxy.onrender.com ./test.py

venv:
	rm -rf venv
	$(PYTHON) -m venv venv
	. venv/bin/activate && \
	pip install -U pip setuptools wheel && \
	pip install -r requirements.txt

.PHONY: check clean run test test-production venv

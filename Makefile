# -*- coding: utf-8-unix -*-

include .env
export

PYTHON = python3.13

check:
	flake8 app.py

clean:
	rm -rf __pycache__

deploy:
	$(MAKE) check
	git push heroku master
	$(MAKE) test-production

run:
	flask --app=app.py run --debug

test:
	./test.py

test-production:
	HOST=`heroku info -s | grep web_url | cut -d= -f2` ./test.py

venv:
	rm -rf venv
	$(PYTHON) -m venv venv
	. venv/bin/activate && \
	  pip install -U pip setuptools wheel && \
	  pip install -r requirements.txt

.PHONY: check clean deploy run test test-production venv

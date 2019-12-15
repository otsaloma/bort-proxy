# -*- coding: utf-8-unix -*-

export FLASK_APP = app.py
export FLASK_ENV = development

check:
	flake8 app.py

clean:
	rm -rf __pycache__

run:
	flask run

test:
	./test.py

test-production:
	HOST=`heroku info -s | grep web_url | cut -d= -f2` ./test.py

venv:
	rm -rf venv
	virtualenv -p python3 venv
	. venv/bin/activate && pip install -r requirements.txt

.PHONY: check clean run test test-production venv

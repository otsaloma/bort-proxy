# -*- coding: utf-8-unix -*-

export FLASK_APP = app.py
export FLASK_DEBUG = 1

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

.PHONY: check clean run test test-production

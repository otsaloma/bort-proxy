# -*- coding: utf-8-unix -*-

include .env
export

check:
	flake8 app.py

clean:
	rm -rf __pycache__

deploy:
	$(MAKE) check
	git push heroku master
	$(MAKE) test-production

run:
	flask run --debug

test:
	./test.py

test-production:
	HOST=`heroku info -s | grep web_url | cut -d= -f2` ./test.py

.PHONY: check clean deploy run test test-production

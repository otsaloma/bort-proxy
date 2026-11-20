# -*- coding: utf-8-unix -*-

include .env
export

check:
	uv run flake8 app.py

clean:
	rm -rf __pycache__

run:
	uv run flask --app=app.py run --debug

test:
	uv run ./test.py

test-production:
	HOST=https://bort-proxy.onrender.com uv run ./test.py

.PHONY: check clean run test test-production

# -*- coding: us-ascii-unix -*-

export FLASK_APP = app.py
export FLASK_DEBUG = 1

check:
	pyflakes app.py

clean:
	rm -rf __pycache__

run:
	flask run

tarball:
	$(MAKE) clean
	tar -C .. -cJf ../`basename $$PWD`-`date +%Y%m%d`.tar.xz `basename $$PWD`

.PHONY: check clean run tarball

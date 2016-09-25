# -*- coding: us-ascii-unix -*-

NAME = `basename $$PWD`

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
	tar -C .. -cJf ../$(NAME)-`date +%Y%m%d`.tar.xz $(NAME)

.PHONY: check clean run tarball

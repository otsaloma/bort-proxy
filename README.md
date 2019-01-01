Bort Proxy
==========

A caching proxy server for [Bort.io](https://bort.io/). Current proxied
data includes website icons and search suggestions.

To try Bort Proxy locally, just install the dependencies, start the
server

```bash
make run
```

and browse to e.g. <http://localhost:5000/icon?url=github.com&size=96>.
Check `app.py` for all API paths and parameters.

Bort Proxy is free software released under the MIT license, see the file
[`COPYING`](COPYING) for details.

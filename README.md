Bort Proxy
==========

A caching proxy server for [Bort.io](https://bort.io/). Current proxied
data includes website icons and search suggestions.

## Development

```bash
make venv
make run
```

Then try e.g. <http://localhost:5000/icon?url=github.com&size=96>.

Check `app.py` for all API endpoints and parameters.

## Production

Run with gunicorn.

```bash
gunicorn app:app --workers 2 --threads 16
```

Define `REDIS_URL` in the environment pointing to a small Redis instance
running with `allkeys-lru` eviction policy.

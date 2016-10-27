Deploying to Heroku
===================

* Set up Heroku with Python and Redis
    - <https://devcenter.heroku.com/categories/python>
    - <https://elements.heroku.com/addons/rediscloud>
* Do final quality checks and upload
    - `make check`
    - `git status`
    - `git push origin master`
    - `git push heroku master`
* Check that server is running OK and clear the Redis cache if needed
    - `./test.py http://XXX.herokuapp.com/`
    - `heroku logs --tail`
    - <https://dashboard.heroku.com/apps>

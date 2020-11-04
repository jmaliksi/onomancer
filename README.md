# onomancer
The name alembic https://onomancer.sibr.dev

# Development
All commands run at project root

## Installation
```
python3 -m venv env
. env/bin/activate
pip install -r requirements.txt
```

## Database setup
ensure virtualenv has been activated
```
mkdir data
python -m onomancer.database clean bootstrap load
```

### Database CLI commands
* `clean` - drops all tables
* `bootstrap` - recreates tables
* `load` - loads in a hardcoded list of egg names to seed the DB
* `purge "$name"` - removes all records containing this name
* `migrate` - performs hardcoded DB migration

## Generate Secrets
```
mkdir data
python -m onomancer.scripts generate_csrf_key generate_mod_key generate_appsecret
```

## Run
ensure virtualenv has been activated
```
python -m onomancer test
```
Server will start up at 0.0.0.0:5001

Icons
* https://game-icons.net/1x1/lorc/crystal-ball.html
* https://game-icons.net/1x1/delapouite/aquarium.html

# API
Onomancer has a public API if you want to use these voted names in your own project.

## Get Name

`/api/getName`

Gets a single name. Same algorithm that serves up names for rating, which is a chance to be a newly formed name or an existing name that's been upvoted.

Rate limit: 10/s


## Get Names

`/api/getNames`

Gets n fully formed names in alphabetical order.

Rate limit: 5/s

Parameters:
* `threshold` - filter names with votes at or above this threshold, default 0
* `limit` - page size, default 100
* `offset` - page offset, default 0
* `random` - returns in random order if set to true, default 0

## Get Eggs

`/api/getEggs`

Gets n individual eggs in alphabetical order.

Rate limit: 5/s

Parameters
* `threshold` - filter names with votes at or above this threshold, default 0
* `limit` - page size, default 100
* `offset` - page offset, default 0
* `random` - returns in random order if set to true, default 0

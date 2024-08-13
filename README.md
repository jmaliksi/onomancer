# onomancer
Distill the ultimate Blaseball name: https://onomancer.sibr.dev

Onomancer lets people submit blaseball names and rate these combinations to distill the ultimate blaseball name. Names are fed through a proprietary\* algorithm to generate a full Blaseball player, and can be used to create your own teams to share with friends.

\*it's just a seeded RNG

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
* https://game-icons.net/1x1/delapouite/acoustic-megaphone.html

# API
Onomancer has a public API if you want to use these voted names in your own project.

## Get Name

`/api/getName`

Gets a single name. Same algorithm that serves up names for rating, which is a chance to be a newly formed name or an existing name that's been upvoted.

Rate limit: 25/s

Parameters:
* `with_stats` - generate FK stats for this name


## Get Names

`/api/getNames`

Gets n fully formed names in alphabetical order.

Rate limit: 10/s

Parameters:
* `threshold` - filter names with votes at or above this threshold, default 0
* `limit` - page size, default 100
* `offset` - page offset, default 0
* `random` - returns in random order if set to true, default 0
* `with_stats` - generate FK stats for each name

## Get Eggs

`/api/getEggs`

Gets n individual eggs in alphabetical order.

Rate limit: 10/s

Parameters:
* `threshold` - filter names with votes at or above this threshold, default 0
* `limit` - page size, default 100
* `offset` - page offset, default 0
* `random` - returns in random order if set to true, default 0
* `first` - filter names annotated as first at or above this threshold, default empty
* `second` - filter names annotated as second at or above this threshold, default empty
* `affinity` - value between -1.0 and 1.0. Negative prefers first annotations, positive for second annotations. Default 0.


## Crawl Names - experimental

`/api/crawlNames/<name>`

Given a name, find like names

Rate limit: 1/s

Parameters:
* `threshold` - filter names with votes at or above this threshold, default 0
* `limit` - page size, default 100
* `fanout` - how many iterations to crawl out, default 2, min 1, max 10

## Crawl Eggs - experimental

`/api/crawlEggs/`

Given a comma separated list of eggs, find names that are related to the vibe

Rate limit: 1/s

Parameters:
* `q` - comma separated list of eggs
* `threshold` - filter names with votes at or above this threshold, default 0
* `fanout` - how many iterations to crawl out, default 3
* `limit` - page size, default 10
* `egg_threshold` - minimum votes an egg must have to be considered for the next iteration of fanout

## Generate Stats

`/api/generateStats/<name>`

Rate limit: 50/s

Given any name, use the letters to seed an RNG to generate FK stats.

`/api/generateStats2`

Rate limit: 50/s

This version properly handles slashes

Parameters:
* `name` - Required

## Get or Generate Stats

`/api/getOrGenerateStats`

Rate limit: 10/s

Given a name, use the letters to seed an RNG to generate FK stats. If the name exists in Blaseball, returns that player info instead. **makes external calls to check for existence, treat with respect**

Parameters:
* `name` - Required


## Get Stats

`/api/getStats/`

Rate limit: 5/s

Given a comma separated lst of guids, returns FK stats for all those names.

Parameters:
* `ids` (required) - comma separated list of guids

## Get Collection

`/api/getCollection`

Given the entire share URL or just share code of a Collection, return a JSON blob representing the team with full player stats.

Rate limit: 5/s

Parameters:
* `token` - Required. Either the full share URL or just the token (ie everything that comes after `shareCollection/` in the share URL). Must be URL encoded.

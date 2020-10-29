# onomancer
Name alembic

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
python -m onomancer.database clean bootstrap load
```

### Database CLI commands
`clean` - drops all tables
`bootstrap` - recreates tables
`load` - loads in a hardcoded list of egg names to seed the DB
`purge "$name"` - removes all records containing this name
`migrate` - performs hardcoded DB migration

## Run
ensure virtualenv has been activated
```
python -m onomancer -test
```
Server will start up at 0.0.0.0:5001

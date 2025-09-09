#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations
python -c "
from backend.database.connection import init_database
init_database()
print('Database initialized successfully!')
"
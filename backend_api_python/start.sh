#!/bin/bash

# QuantDinger Python API startup script

# Activate the virtual environment if one is used
# source venv/bin/activate

# Check whether dependencies are installed
if ! python -c "import flask" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Start the service
echo "Starting QuantDinger Python API service..."
echo "Service address: http://0.0.0.0:5000"

# Create the log directory
mkdir -p logs

# Development environment (uses the new entry file)
python run.py

# Production environment (uses gunicorn)
# gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 --access-logfile logs/access.log --error-logfile logs/error.log "run:create_app()"

#!/bin/bash

# Navigeer naar de juiste directory
cd "$(dirname "$0")"

# Activeer virtual environment
source venv/bin/activate

# Start Flask app
python app.py

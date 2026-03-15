#!/bin/bash

echo "Starting AI Agent..."
python agent.py &

echo "Starting Flask Server..."
gunicorn app:app
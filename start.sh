#!/bin/bash

echo "Starting AI Agent..."
python agent.py dev &

echo "Starting Flask Server..."
exec gunicorn app:app
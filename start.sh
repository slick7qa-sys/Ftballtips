#!/usr/bin/env bash
# Make sure this file is executable: chmod +x start.sh
exec gunicorn -w 4 -b 0.0.0.0:$PORT main:app

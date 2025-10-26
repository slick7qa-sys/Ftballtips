#!/usr/bin/env bash
# Make sure script is executable: chmod +x start.sh

# Start Gunicorn with 4 workers, listening on the port Render provides
exec gunicorn -w 4 -b 0.0.0.0:$PORT main:app

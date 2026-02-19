#!/bin/bash
cd /Users/sylvain/_MACARON-SOFTWARE/_SOFTWARE_FACTORY
while true; do
    echo "[$(date)] Starting platform server..."
    python3 -m uvicorn platform.server:app --host 127.0.0.1 --port 8090 --ws none 2>&1
    EXIT_CODE=$?
    echo "[$(date)] Server exited with code $EXIT_CODE — restarting in 2s..."
    sleep 2
done

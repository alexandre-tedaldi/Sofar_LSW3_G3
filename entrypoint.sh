#!/bin/bash
nginx
while true; do
  python3 /app/InverterData.py
  sleep 60
done

#!/usr/bin/env python3
"""
Prometheus HTTP Exporter for Sofar inverter.
Executes InverterData.py on each scrape and serves the prometheus metrics file.

Usage:
  python3 InverterExporter.py [--port 9100]
"""

import sys
import os
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from zoneinfo import ZoneInfo
import configparser

script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(script_dir)

configParser = configparser.RawConfigParser()
configParser.read('./config.cfg')
tz = ZoneInfo(configParser.get('SofarInverter', 'timezone'))
prometheus_file = configParser.get('Prometheus', 'prometheus_file')

LISTEN_PORT = 9100
if '--port' in sys.argv:
    LISTEN_PORT = int(sys.argv[sys.argv.index('--port') + 1])


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics' or self.path == '/':
            # Run InverterData.py which writes the prometheus metrics file
            result = subprocess.run(
                [sys.executable, os.path.join(script_dir, 'InverterData.py')],
                cwd=script_dir,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                metrics = f"# error running InverterData.py: {result.stderr or result.stdout}\n"
            else:
                # Read the metrics file it generated
                try:
                    with open(prometheus_file, 'r') as f:
                        metrics = f.read()
                except FileNotFoundError:
                    metrics = f"# metrics file not found: {prometheus_file}\n"

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(metrics.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        ts = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts}] {args[0]}")


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', LISTEN_PORT), MetricsHandler)
    print(f"Sofar Inverter Exporter listening on port {LISTEN_PORT}")
    print(f"Metrics endpoint: http://0.0.0.0:{LISTEN_PORT}/metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()

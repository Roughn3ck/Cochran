#!/usr/bin/env python3
"""Cochran Live Dashboard - HTTP server with mode switching"""
import http.server
import json
import os
import time
import threading

TRANSCRIPT = '/tmp/cochran/transcript.txt'
RESPONSE = '/tmp/cochran/last_response.txt'
MODE_FILE = '/tmp/cochran/mode.txt'
LATENCY_FILE = '/tmp/cochran/latency.txt'

class CochranHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress access logs

    def do_GET(self):
        if self.path == '/api/status':
            transcript = ''
            response = ''
            latency = ''
            try:
                with open(TRANSCRIPT, 'r') as f:
                    transcript = f.read()
            except: pass
            try:
                with open(RESPONSE, 'r') as f:
                    response = f.read()
            except: pass
            try:
                with open(LATENCY_FILE, 'r') as f:
                    latency = f.read().strip()
            except: pass
            try:
                with open(MODE_FILE, 'r') as f:
                    current_mode = f.read().strip()
            except:
                current_mode = 'private'

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'transcript': transcript,
                'response': response,
                'latency': latency,
                'mode': current_mode,
                'time': time.strftime('%H:%M:%S')
            }).encode())
        elif self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            with open(os.path.join(os.path.dirname(__file__), 'dashboard.html'), 'rb') as f:
                self.wfile.write(f.read())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/mode':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                mode = data.get('mode', 'private')
                with open(MODE_FILE, 'w') as f:
                    f.write(mode)
                print(f'[DASHBOARD] Mode changed to: {mode}')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'mode': mode}).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

if __name__ == '__main__':
    os.makedirs('/tmp/cochran', exist_ok=True)
    # Write default mode
    if not os.path.exists(MODE_FILE):
        with open(MODE_FILE, 'w') as f:
            f.write('private')
    server = http.server.HTTPServer(('0.0.0.0', 8765), CochranHandler)
    print('[DASHBOARD] Cochran Live Dashboard on http://localhost:8765')
    print('[DASHBOARD] Mode switching: Private Counsel / Court Open / Default / Mute')
    server.serve_forever()
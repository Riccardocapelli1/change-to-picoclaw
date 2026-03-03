import http.server
import json
import urllib.request
import urllib.error
import os
import sys

class GroqProxy(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            cl_header = self.headers.get("Content-Length", "0")
            content_length = int(cl_header)
            body = self.rfile.read(content_length)
            
            data = json.loads(body)
            
            if "prompt_cache_key" in data:
                del data["prompt_cache_key"]
            
            # Forward the request to Groq
            groq_url = "https://api.groq.com/openai" + self.path
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.headers.get("Authorization", ""),
                "User-Agent": "Mozilla/5.0"
            }
            
            req = urllib.request.Request(groq_url, data=json.dumps(data).encode(), headers=headers, method="POST")
            
            try:
                with urllib.request.urlopen(req) as resp:
                    resp_status = resp.status
                    resp_headers = resp.info()
                    resp_body = resp.read()
                    
                    self.send_response(resp_status)
                    for k, v in resp_headers.items():
                        if k.lower() not in ["content-encoding", "transfer-encoding", "content-length"]:
                            self.send_header(k, v)
                    
                    self.send_header("Content-Length", str(len(resp_body)))
                    self.end_headers()
                    self.wfile.write(resp_body)
                    
            except urllib.error.HTTPError as e:
                resp_body = e.read()
                self.send_response(e.code)
                for k, v in e.headers.items():
                    if k.lower() not in ["content-encoding", "transfer-encoding", "content-length"]:
                        self.send_header(k, v)
                
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
                
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", 18795), GroqProxy)
    print("Groq Proxy started on port 18795")
    server.serve_forever()

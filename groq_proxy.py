import http.server
import json
import urllib.request
import urllib.error
import os
import sys
import re
import time

class GroqProxy(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            cl_header = self.headers.get("Content-Length", "0")
            content_length = int(cl_header)
            body = self.rfile.read(content_length)
            
            data = json.loads(body)
            
            # 1. Remap models to Groq-native formats
            requested_model = data.get("model", "")
            if "gpt-oss-120b" in requested_model:
                data["model"] = "openai/gpt-oss-120b"
            elif "compound" in requested_model:
                data["model"] = "groq/compound"
            elif "llama-3.3-70b-versatile" in requested_model:
                data["model"] = "llama-3.3-70b-versatile"
            
            # 2. Remove unsupported 'prompt_cache_key' from Picoclaw v0.2.0
            if "prompt_cache_key" in data:
                del data["prompt_cache_key"]
            
            # Forward the request to Groq API
            groq_url = "https://api.groq.com/openai" + self.path
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.headers.get("Authorization", ""),
                "User-Agent": "PicoClaw-Groq-Proxy/1.0"
            }
            
            req = urllib.request.Request(groq_url, data=json.dumps(data).encode(), headers=headers, method="POST")
            
            try:
                with urllib.request.urlopen(req) as resp:
                    self.send_response(resp.status)
                    for k, v in resp.info().items():
                        if k.lower() not in ["content-encoding", "transfer-encoding", "content-length"]:
                            self.send_header(k, v)
                    
                    resp_body = resp.read()
                    self.send_header("Content-Length", str(len(resp_body)))
                    self.end_headers()
                    self.wfile.write(resp_body)
                    
            except urllib.error.HTTPError as e:
                resp_body = e.read()
                
                # RECOVERY LOGIC: Catch tool call hallucinations rejected by Groq
                try:
                    err_json = json.loads(resp_body)
                    if err_json.get("error", {}).get("code") == "tool_use_failed":
                        failed_gen = err_json.get("error", {}).get("failed_generation", "")
                        
                        # Match: <function=name({"arg": "val"})</function>
                        match = re.search(r'<function=([\w-]+).*?(\{.*?\})', failed_gen, re.DOTALL)
                        if not match:
                             match = re.search(r'<function=([\w-]+).*?\((.*?)\)', failed_gen, re.DOTALL)
                        
                        if match:
                            tool_name = match.group(1)
                            tool_args_str = match.group(2)
                            
                            print(f"RECOVERY: Fixing hallucinated tool call: {tool_name}", file=sys.stderr)
                            
                            fake_resp = {
                                "id": "chatcmpl-recovery-" + os.urandom(4).hex(),
                                "object": "chat.completion",
                                "created": int(time.time()),
                                "model": data.get("model", "llama-3.3-70b-versatile"),
                                "choices": [
                                    {
                                        "index": 0,
                                        "message": {
                                            "role": "assistant",
                                            "content": None,
                                            "tool_calls": [
                                                {
                                                    "id": "call_" + os.urandom(4).hex(),
                                                    "type": "function",
                                                    "function": {
                                                        "name": tool_name,
                                                        "arguments": tool_args_str
                                                    }
                                                }
                                            ]
                                        },
                                        "finish_reason": "tool_calls"
                                    }
                                ],
                                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                            }
                            
                            resp_json = json.dumps(fake_resp).encode()
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.send_header("Content-Length", str(len(resp_json)))
                            self.end_headers()
                            self.wfile.write(resp_json)
                            return
                except:
                    pass

                # Normal Error Forwarding (e.g., 429 Rate Limits)
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
    print("Self-healing Groq Proxy (v4) started on port 18795")
    server.serve_forever()

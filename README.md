# Picoclaw Groq Integration Fix

This repository documents the changes and workarounds applied to successfully integrate [PicoClaw](https://github.com/sipeed/picoclaw) with the Groq API on a remote VPS.

## The Issue
PicoClaw v0.2.0 (and current main) sends a `prompt_cache_key` parameter in its OpenAI-compatible provider calls. While OpenAI supports this, **Groq rejects requests** containing this field with a 400 Bad Request error.

## The Solution
Since we were working with a precompiled binary and missing a build environment on the target machine, we implemented a **Lightweight Python Proxy** that intercepts calls to Groq and strips the unsupported parameter.

### 1. The Proxy Script (`groq_proxy.py`)
This script runs locally on the VPS (default port `18795`) and forwards requests to `api.groq.com/openai`, removing the problematic field.

```python
import http.server
import json
import urllib.request
import urllib.error
import os
import sys
import re

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
```

### 2. PicoClaw Configuration (`~/.picoclaw/config.json`)
Update the `api_base` for your Groq model to point to the local proxy:

```json
{
  "model_list": [
    {
      "model_name": "llama-3.3-70b-versatile",
      "model": "groq/llama-3.3-70b-versatile",
      "api_base": "http://127.0.0.1:18795/v1",
      "api_key": "your_groq_api_key"
    }
  ],
  "agents": {
    "defaults": {
      "model": "llama-3.3-70b-versatile"
    }
  }
}
```

### 3. Native Tool-Calling Enforcement
Some models might try to use pseudo-tags (like `<function=...>` or `tool_use`). To prevent this, we added an instruction to `~/.picoclaw/workspace/AGENTS.md`:

```markdown
## Tool Usage
You MUST use the native JSON tool-calling format. 
DO NOT use custom tags like `<function=...>` or `<tool_call>...`.
Only use tools when you specifically need their functionality.
```

## Replication Steps
1. Install `picoclaw` binary.
2. Run `picoclaw onboard`.
3. Start the Python proxy: `nohup python3 groq_proxy.py > groq_proxy.log 2>&1 &`.
4. Configure `~/.picoclaw/config.json` with your Groq key and point it to `http://127.0.0.1:18795/v1`.
5. Run `picoclaw agent`.

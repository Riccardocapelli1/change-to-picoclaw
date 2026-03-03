# PicoClaw 🦞 Groq & Telegram VPS Fix (IPv6-Only)

This repository providing solutions and workarounds for running **PicoClaw v0.2.0** on minimal VPS environments (e.g., IPv6-only) using **Groq API**.

## 🚀 The Problem
1. **IPv6-Only Connectivity**: PicoClaw fails to reach Telegram (IPv4) on pure IPv6 servers.
2. **Groq API Compatibility**: PicoClaw sends `prompt_cache_key`, which Groq rejects (400 Bad Request).
3. **Model Hallucinations**: Older models (8B) or buggy tool-calls are rejected by Groq's strict schema.

## 🛠️ Components

### 1. `groq_proxy.py` (Self-Healing Proxy)
Runs on port `18795`. It solves:
- **Parameter Stripping**: Removes `prompt_cache_key`.
- **Model Remapping**: Allows using generic model names while mapping to `groq/compound` or `openai/gpt-oss-120b`.
- **Self-Healing**: Intercepts `tool_use_failed` errors from Groq (hallucinated tags like `<function=...>`) and reformats them into valid OpenAI tool-calling JSON for Picoclaw.

### 2. `socks5_proxy.py` (Telegram Bridge)
Runs on port `18797`. It solves:
- **IPv4 Bridge**: Allows the Telegram channel to work on IPv6-only servers by bridging the requests through Python's dual-stack sockets.

## 📋 Installation & Setup

1. **Upload Scripts** to your VPS home directory (`~/`).
2. **Start Services** (Recommended to use `screen` or `nohup`):
   ```bash
   nohup python3 ~/groq_proxy.py >> ~/groq_proxy.log 2>&1 &
   nohup python3 ~/socks5_proxy.py >> ~/socks5_proxy.log 2>&1 &
   ```
3. **Update `~/.picoclaw/config.json`**:
   
   **Telegram Section**:
   ```json
   "telegram": {
     "enabled": true,
     "token": "YOUR_BOT_TOKEN",
     "proxy": "socks5://127.0.0.1:18797",
     "allow_from": ["*"]
   }
   ```

   **Model Section**:
   ```json
   {
     "model_name": "stable-model",
     "model": "llama-3.3-70b-versatile",
     "api_base": "http://127.0.0.1:18795/v1",
     "api_key": "YOUR_GROQ_API_KEY"
   }
   ```

## ⚠️ Important Note on Rate Limits
Using **Llama-3.1-8b-instant** on Groq Free Tier (Limit 6,000 TPM) often results in **429 errors** because Picoclaw system prompts are large. It is highly recommended to use **`llama-3.3-70b-versatile`** (Limit 30,000+ TPM).

## ✅ Testing
```bash
# Test through the proxy
picoclaw agent -m "Hello, are you using the proxy?"

# Check gateway logs
tail -f ~/picoclaw_gateway.log
```

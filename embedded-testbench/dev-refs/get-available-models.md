You definitely don't need to download Postman or any heavy API clients just to run a couple of basic checks. 

Here is the absolute fastest way to check your available models right now, using tools already built into your computer.

### 1. For Google Gemini: Your Web Browser
Because Google allows you to pass the API key directly in the URL (as a query parameter), you don't even need a terminal.

1. Open a new tab in Chrome, Firefox, Safari, etc.
2. Paste this exact URL, replacing `YOUR_KEY` with your actual API key:
   `https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY`
3. Hit Enter. You'll instantly see a text file (JSON) listing every model your key has access to.

### 2. For OpenAI (and Gemini): The Terminal / Command Prompt (`curl`)
OpenAI requires you to send your API key as a "Header," which you can't do in a standard browser address bar. Fortunately, almost every modern operating system (Windows, Mac, Linux) has a built-in tool called `curl` that handles this perfectly.

Open your **Command Prompt** (Windows) or **Terminal** (Mac/Linux) and paste these commands:

**For OpenAI:**
```bash
curl https://api.openai.com/v1/models -H "Authorization: Bearer YOUR_OPENAI_KEY"
```

**For Google Gemini (if you prefer the terminal over the browser):**
```bash
curl "https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_GEMINI_KEY"
```
*(Note: If you are on Windows PowerShell, sometimes `curl` is aliased awkwardly. If the above fails in PowerShell, type `cmd` and hit enter to switch to the classic command prompt, then run it).*

### 3. The "Helper Script" Route (Python)
If you're already working inside a code repository and prefer to just run a quick script like Codex suggested, here is a tiny Python script that does exactly what you need. Just save it as `check_models.py` and run it:

```python
import urllib.request
import json

# --- ADD YOUR KEYS HERE ---
OPENAI_KEY = "sk-..." 
GEMINI_KEY = "AI..."

def check_openai():
    req = urllib.request.Request("https://api.openai.com/v1/models")
    req.add_header("Authorization", f"Bearer {OPENAI_KEY}")
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read())
        print("✅ OpenAI Models:", [m['id'] for m in data['data']])
    except Exception as e:
        print("❌ OpenAI Error:", e)

def check_gemini():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
        print("✅ Gemini Models:", [m['name'] for m in data['models']])
    except Exception as e:
        print("❌ Gemini Error:", e)

print("Fetching models...\n")
if OPENAI_KEY != "sk-...": check_openai()
if GEMINI_KEY != "AI...": check_gemini()
```

**The TL;DR:** Paste the Google link in your browser, and paste the OpenAI `curl` command in your terminal. You'll have your answers in about 15 seconds!
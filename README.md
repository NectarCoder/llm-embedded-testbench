# Arduino Assistant

A VS Code / Arduino IDE 2 extension that wraps the [LLM Embedded Workbench](https://github.com/NectarCoder/llm-embedded-workbench) in a sidebar UI — letting you run generate → compile → self-debug experiments against cloud and local LLMs without touching the terminal.

---

## What It Does

The extension provides a sidebar panel that lets you:

- Select a task from your `llm_prompts.json`
- Choose a prompt style (simple, structured, or both)
- Choose a provider mode (default, cloud, local, or all)
- Configure retries, repetitions, board FQBN, and more
- Watch the compile loop stream live in the log panel
- Copy the last generated `.ino` sketch to your clipboard
- Open the results folder directly from the UI

All experiment logic lives in your existing `testbench.py` — the extension just drives it and displays the output.

---

## Requirements

- [VS Code](https://code.visualstudio.com/) 1.116+ **or** [Arduino IDE 2](https://www.arduino.cc/en/software)
- Python 3.9+
- [arduino-cli](https://arduino.github.io/arduino-cli/) installed and configured
- A `.venv` virtualenv in your testbench project root with dependencies installed
- API keys set as environment variables (for cloud providers)

---

## Project Structure

This repo contains two things side by side:

```
arduino-assistant/        ← VS Code extension (this repo)
├── src/
│   └── extension.ts
├── media/
│   └── icon.svg
├── scripts/
│   └── deploy.sh
├── package.json
└── tsconfig.json

your-testbench-project/   ← Your existing Python testbench (separate folder)
├── testbench.py
├── run_config.json
├── llm_prompts.json
├── requirements.txt
└── .venv/
```

The extension reads `run_config.json` and `llm_prompts.json` from whatever folder is open as your workspace, then spawns `testbench.py` using the `.venv` Python in that same folder.

---

## Setup

### 1. Clone and install extension dependencies

```bash
git clone https://github.com/yourname/arduino-assistant
cd arduino-assistant
npm install
```

### 2. Set up your testbench project virtualenv

In your **testbench project folder** (not the extension folder):

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure arduino-cli

```bash
arduino-cli version
arduino-cli config init
arduino-cli core update-index
arduino-cli core install arduino:avr   # or whichever core your board needs
```

### 4. Set API key environment variables

**macOS / Linux (zsh/bash):**
```bash
export OPENAI_API_KEY="your_openai_key"
export GOOGLE_API_KEY="your_google_key"
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="your_openai_key"
$env:GOOGLE_API_KEY="your_google_key"
```

For Ollama (local), no API key is needed. Set `OLLAMA_BASE_URL` if your server isn't on the default `http://127.0.0.1:11434`:

```bash
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
```

---

## run_config.json Schema

The extension reads this file to populate the provider mode descriptions and apply UI overrides before each run. It expects the `provider_profiles` structure:

```json
{
  "provider_profiles": {
    "default": [
      { "name": "openai", "model": "gpt-4o", "temperature": 0.2 }
    ],
    "cloud": [
      { "name": "openai", "model": "gpt-4o", "temperature": 0.2 },
      { "name": "google", "model": "gemini-1.5-pro", "temperature": 0.2 }
    ],
    "local": [
      { "name": "ollama", "model": "deepseek-coder:6.7b", "temperature": 0.2 }
    ],
    "all": [
      { "name": "openai", "model": "gpt-4o", "temperature": 0.2 },
      { "name": "google", "model": "gemini-1.5-pro", "temperature": 0.2 },
      { "name": "ollama", "model": "deepseek-coder:6.7b", "temperature": 0.2 }
    ]
  },
  "prompt_styles": ["simple"],
  "repetitions": 1,
  "max_debug_retries": 5,
  "request_timeout_seconds": 300,
  "request_reset_retry_count": 1,
  "compile_timeout_seconds": 60,
  "output_root": "results",
  "arduino": {
    "fqbn": "arduino:avr:mega",
    "port": ""
  }
}
```

---

## llm_prompts.json Schema

```json
{
  "tasks": [
    {
      "name": "task1_warmup_led_serial",
      "simple_prompt": "Write an Arduino sketch that blinks the built-in LED and prints 'hello' over Serial at 9600 baud.",
      "structured_prompt": "Write a complete Arduino sketch (.ino) for an Arduino Mega 2560 that: (1) blinks the built-in LED on pin 13 at 1Hz, (2) prints 'hello' to Serial at 9600 baud once per second. Return only the code in a fenced cpp block."
    }
  ]
}
```

---

## Development (VS Code)

### Run in the Extension Development Host

Press **F5** in VS Code. This opens a second window with the extension loaded.

To automatically open your testbench project in that window every time, edit `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Run Extension",
      "type": "extensionHost",
      "request": "launch",
      "args": [
        "--extensionDevelopmentPath=${workspaceFolder}",
        "/absolute/path/to/your/testbench/project"
      ]
    }
  ]
}
```

### Compile

```bash
npm run compile
```

### Watch mode (recompiles on save)

```bash
npm run watch
```

---

## Installing in Arduino IDE 2

### Package the extension

```bash
npm install -g @vscode/vsce
npm run compile
vsce package
```

This produces `arduino-assistant-x.x.x.vsix`.

### Install via the deploy script

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

Then **fully quit and relaunch Arduino IDE 2**. The sidebar icon will appear in the activity bar.

### Manual install

```bash
PLUGIN_DIR="$HOME/.arduinoIDE/plugins/arduino-assistant"
mkdir -p "$PLUGIN_DIR"
cp arduino-assistant-*.vsix "$PLUGIN_DIR/"
cd "$PLUGIN_DIR"
unzip -o arduino-assistant-*.vsix
```

**Windows:**
```powershell
$dest = "$env:APPDATA\.arduinoIDE\plugins\arduino-assistant"
New-Item -ItemType Directory -Force -Path $dest
Copy-Item arduino-assistant-*.vsix $dest
cd $dest
Expand-Archive -Force arduino-assistant-*.vsix .
```

---

## Using the Sidebar

| Control | Description |
|---|---|
| **Task** | Populated from `llm_prompts.json` in the open workspace |
| **Prompt style** | Simple, structured, or both (runs twice) |
| **Provider mode** | Maps to `--cloud`, `--local`, `--all`, or the default profile |
| **Retries** | Max self-debug iterations after initial generation (maps to `max_debug_retries`) |
| **Repetitions** | How many times to repeat each condition |
| **Board FQBN** | Forwarded to `arduino-cli compile --fqbn` |
| **Run experiment** | Spawns `testbench.py` and streams output to the log panel |
| **Copy generated sketch** | Copies the last generated `.ino` to your clipboard |
| **Open results folder** | Reveals the `results/` directory in Finder / Explorer |

The log panel color-codes output automatically: green for success, red for errors, yellow for retries and warnings.

---

## How It Works

When you click **Run experiment**, the extension:

1. Reads your `run_config.json` and `llm_prompts.json`
2. Backs up both files in memory
3. Writes overridden versions to disk (applying your UI settings)
4. Spawns `.venv/bin/python -u testbench.py [--cloud|--local|--all]`
5. Streams stdout and stderr line-by-line into the log panel
6. Restores the original config files when the process exits
7. Finds the highest-iteration `.ino` in `results/` and enables the copy button

Your `testbench.py` is never modified and runs exactly as it would from the terminal.

---

## Troubleshooting

**Sidebar shows no tasks / providers**
Open your testbench project folder in VS Code first (`File → Open Folder`). The extension reads config from `workspaceFolders[0]`.

**"venv not found" error**
Make sure `.venv` exists in your testbench project root. Run:
```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

**Stuck on "running" with no logs**
Open **Help → Toggle Developer Tools → Console** in the Extension Development Host to see errors. Also check that `testbench.py` flushes stdout — pass `-u` to Python (the extension does this automatically).

**arduino-cli not found**
The subprocess inherits the extension host's PATH. If `arduino-cli` is installed but not found, add it to your shell profile (`~/.zshrc`, `~/.bashrc`) and restart VS Code.

**API key errors**
Environment variables must be set before VS Code launches — setting them in a terminal after VS Code is open won't work. Add them to your shell profile or use a `.env` loader.

---

## Roadmap

- [ ] Folder picker so the testbench path can be set explicitly (needed for Arduino IDE 2 where the workspace is the sketch folder)
- [ ] Live metrics pulled from CSV as runs complete
- [ ] Results history viewer showing past runs from `results.json`
- [ ] Hardware upload phase when `deploy_stub` is replaced
- [ ] VS Code setting for testbench project path

---

## License

MIT
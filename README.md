# LLM Embedded System Testbench

This repository is an experiment runner designed for structured prompting and iterative self-debugging experiments, using LLMs to generate and refine Arduino code.

Forked from https://github.com/anonimwut/llm-embedded-testbench  
Original work citation:  
> Z. Englhardt et al., ‘Exploring and characterizing large language models for embedded system development and debugging’, in Extended Abstracts of the CHI Conference on Human Factors in Computing Systems, Honolulu HI USA, 2024, pp. 1–9.

## Current Scope

The active pipeline is compile-only by design:

1. Generate Arduino code from local and cloud LLMs.
2. Compile with arduino-cli.
3. If compile fails, feed compiler errors back to the model.
4. Retry up to 5 repair iterations (6 total generation attempts counting the original prompt).
5. Stop early when compile succeeds.

Hardware upload and runtime validation are intentionally stubbed for the next phase.

## Supported Providers

- OpenAI API
- Google Gemini API
- Ollama local API (default `http://127.0.0.1:11434`)

## Setup (venv + pip)

1. Create and activate a virtual environment.
    - `python -m venv .venv`
    - `.venv\Scripts\activate` (Windows)
    - `source .venv/bin/activate` (UNIX)
2. Install dependencies:
     - `pip install -r requirements.txt`
3. Install arduino-cli.
    - `winget install ArduinoSA.CLI` (Windows)
    - `brew install arduino-cli` (macOS with Homebrew)
    - `sudo port install arduino-cli` (macOS with MacPorts)
4. Configure arduino-cli:
    - `arduino-cli version`
    - `arduino-cli config init`
    - `arduino-cli core update-index`
    - TODO: commands to setup the exact board (see dev-refs/install-and-config-arduino-cli.md)
5. Setup Ollama for using **local** models:
    - Install Ollama from https://ollama.com/download
    - Start the Ollama server (if it is not already running):
        - `ollama serve`
    - Pull required local models:
        - `ollama pull llama3.1:8b`
        - `ollama pull gemma2:9b`
        - `ollama pull deepseek-r1:8b`
    - Verify models are available:
        - `ollama list`
6. Set environment variables for **cloud** model API credentials:
    - OPENAI_API_KEY
    - GOOGLE_API_KEY

PowerShell example:
- `$env:OPENAI_API_KEY="your_openai_key"`
- `$env:GOOGLE_API_KEY="your_google_key"`

ZSH/BASH example:
- `export OPENAI_API_KEY="your_openai_key"`
- `export GOOGLE_API_KEY="your_google_key"`

## Files

- testbench.py: main compile-first experiment runner
- run_config.json: execution settings, provider profiles (default/local/cloud/all), retries, timeout, board config
- llm_prompts.json: task definitions with simple_prompt and structured_prompt

## Prompt File Schema

llm_prompts.json expects:

```json
{
    "tasks": [
        {
            "name": "task_name",
            "simple_prompt": "...",
            "structured_prompt": "..."
        }
    ]
}
```

## Run Configuration Schema

run_config.json includes:

- provider_profiles.default: default run (gemma2:9b local)
- provider_profiles.local: local Ollama-only set
- provider_profiles.cloud: cloud-only set
- provider_profiles.all: local + cloud set
- prompt_styles: ["simple", "structured"]
- repetitions: runs per provider-task-style condition
- max_debug_retries: repair retries after initial generation (5 by default)
- request_timeout_seconds: model timeout (300 for 5 minutes)
- request_reset_retry_count: how many full request resets after timeout (1 by default)
- compile_timeout_seconds: compile timeout per iteration
- output_root: output directory (set to results)
- arduino.fqbn: board fqbn (for Mega 2560 use arduino:avr:mega)
- arduino.port: currently only used in deployment stub metadata

## Running Experiments

Run with defaults:

- python testbench.py

Run all local + cloud profiles:

- python testbench.py --all

Run only cloud profiles:

- python testbench.py --cloud

Run only local Ollama profiles:

- python testbench.py --local

Notes:

- The runner always uses run_config.json and llm_prompts.json from the project root.
- No config/prompts path flags are used in this simplified workflow.

## Timeout and Retry Policy

- If a model request exceeds 5 minutes, it is aborted.
- The runner performs one reset/retry for that same request.
- If the retry also fails, the run is recorded as model_timeout.

## Outputs (CSV-first)

Each run creates a timestamped directory under results/ with:

- results_detailed.csv: per-iteration trace (prompt style, iteration index, compile outcome, latencies, stop reason)
- results_summary.csv: per-condition aggregate metrics
- programs/: generated sketches by run and iteration
- compile_logs/: compiler logs and deploy stub metadata

results/results.json is updated with a full run history (latest first), including ISO and human-readable timestamps and output paths.

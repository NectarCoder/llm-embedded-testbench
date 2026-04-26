# LLM Embedded System Testbench

This repository now includes a compile-first experiment runner designed for structured prompting and iterative self-debugging experiments.

## Current Scope

The active pipeline is compile-only by design:

1. Generate Arduino code from cloud LLMs.
2. Compile with arduino-cli.
3. If compile fails, feed compiler errors back to the model.
4. Retry up to 5 repair iterations (6 total generation attempts counting the original prompt).
5. Stop early when compile succeeds.

Hardware upload and runtime validation are intentionally stubbed for the next phase.

## Supported Providers

- OpenAI API
- Google Gemini API

## Setup (venv + pip)

1. Create and activate a virtual environment.
    - python -m venv .venv
    - .venv\Scripts\activate (Windows)
    - source .venv/bin/activate (UNIX)
2. Install dependencies:
     - pip install -r requirements.txt
3. Install arduino-cli.
    - winget install ArduinoSA.CLI (Windows)
    - brew install arduino-cli (macOS with Homebrew)
    - sudo port install arduino-cli (macOS with MacPorts)
4. Configure arduino-cli:
    - arduino-cli version
    - arduino-cli config init
    - arduino-cli core update-index
    - TODO: commands to setup the exact board (see dev-refs/install-and-config-arduino-cli.md)
5. Set environment variables for API credentials:
     - OPENAI_API_KEY
     - GOOGLE_API_KEY

PowerShell example:
- $env:OPENAI_API_KEY="your_openai_key"
- $env:GOOGLE_API_KEY="your_google_key"

ZSH/BASH example:
- export OPENAI_API_KEY="your_openai_key"
- export GOOGLE_API_KEY="your_google_key"

## Files

- testbench.py: main compile-first experiment runner
- run_config.json: execution settings, providers, retries, timeout, board config
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

- providers: provider/model/temperature list
- prompt_styles: ["simple", "structured"]
- repetitions: runs per provider-task-style condition
- max_debug_retries: repair retries after initial generation (5 by default)
- request_timeout_seconds: model timeout (300 for 5 minutes)
- request_reset_retry_count: how many full request resets after timeout (1 by default)
- compile_timeout_seconds: compile timeout per iteration
- output_root: output directory
- arduino.fqbn: board fqbn (for Mega 2560 use arduino:avr:mega)
- arduino.port: currently only used in deployment stub metadata

## Running Experiments

Run with defaults:

- python testbench.py

Custom paths:

- python testbench.py --config run_config.json --prompts llm_prompts.json

## Timeout and Retry Policy

- If a model request exceeds 5 minutes, it is aborted.
- The runner performs one reset/retry for that same request.
- If the retry also fails, the run is recorded as model_timeout.

## Outputs (CSV-first)

Each run creates a timestamped directory under runs/ with:

- results_detailed.csv: per-iteration trace (prompt style, iteration index, compile outcome, latencies, stop reason)
- results_summary.csv: per-condition aggregate metrics
- programs/: generated sketches by run and iteration
- compile_logs/: compiler logs and deploy stub metadata

runs/results.json is updated with a full run history (latest first), including ISO and human-readable timestamps and output paths.

## Next Phase

When ready, replace deploy_stub in testbench.py with real board upload and runtime validators.

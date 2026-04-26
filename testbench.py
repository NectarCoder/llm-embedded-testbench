import argparse
import csv
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import requests


DEFAULT_CONFIG_PATH = "run_config.json"
DEFAULT_PROMPTS_PATH = "llm_prompts.json"


@dataclass
class ProviderConfig:
    name: str
    model: str
    temperature: float


class ApiRequestError(RuntimeError):
    def __init__(self, category: str, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.retryable = retryable


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name)


def sanitize_error_message(message: str) -> str:
    redacted = re.sub(r"([?&](?:key|api_key)=)[^&\s]+", r"\1<redacted>", message, flags=re.IGNORECASE)
    redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9._-]+", r"\1<redacted>", redacted)
    return redacted


def parse_openai_http_error(response: requests.Response) -> Tuple[str, str, bool]:
    status = response.status_code
    err_type = ""
    err_code = ""
    message = ""

    try:
        payload = response.json()
        if isinstance(payload, dict):
            error_obj = payload.get("error", {})
            if isinstance(error_obj, dict):
                err_type = str(error_obj.get("type", "")).strip()
                err_code = str(error_obj.get("code", "")).strip()
                message = str(error_obj.get("message", "")).strip()
    except ValueError:
        pass

    if not message:
        message = (response.text or f"HTTP {status}").strip()

    detail = sanitize_error_message(message)
    detail_lower = detail.lower()

    is_quota = (
        err_code in {"insufficient_quota", "billing_hard_limit_reached"}
        or "insufficient quota" in detail_lower
        or "billing hard limit" in detail_lower
        or "prepaid" in detail_lower
        or "prepayment" in detail_lower
    )
    is_rate_limited = status == 429 and not is_quota
    retryable = status in {408, 409, 429, 500, 502, 503, 504} and not is_quota

    if is_quota:
        category = "quota_exhausted"
    elif is_rate_limited:
        category = "rate_limited"
    else:
        category = "error"

    qualifiers = ", ".join(part for part in [err_type, err_code] if part)
    prefix = f"OpenAI HTTP {status}"
    if qualifiers:
        prefix = f"{prefix} ({qualifiers})"

    return category, f"{prefix}: {detail}", retryable


def parse_google_http_error(response: requests.Response) -> Tuple[str, str, bool]:
    status = response.status_code
    status_text = ""
    message = ""

    try:
        payload = response.json()
        if isinstance(payload, dict):
            error_obj = payload.get("error", {})
            if isinstance(error_obj, dict):
                status_text = str(error_obj.get("status", "")).strip()
                message = str(error_obj.get("message", "")).strip()
    except ValueError:
        pass

    if not message:
        message = (response.text or f"HTTP {status}").strip()

    detail = sanitize_error_message(message)
    detail_lower = detail.lower()

    is_rate_limited = status == 429 and any(
        marker in detail_lower
        for marker in ["rate limit", "too many requests", "per minute", "per second", "qps"]
    )
    is_quota = (
        "quota" in detail_lower
        or "billing" in detail_lower
        or "prepaid" in detail_lower
        or "prepayment" in detail_lower
    ) and not is_rate_limited
    retryable = status in {408, 409, 429, 500, 502, 503, 504} and not is_quota

    if is_quota:
        category = "quota_exhausted"
    elif status == 429:
        category = "rate_limited"
    else:
        category = "error"

    prefix = f"Google HTTP {status}"
    if status_text:
        prefix = f"{prefix} ({status_text})"

    return category, f"{prefix}: {detail}", retryable


def extract_code(text: str) -> str:
    fenced_pattern = r"```(?:cpp|c\+\+|c|arduino)?\s*([\s\S]*?)```"
    blocks = re.findall(fenced_pattern, text, flags=re.IGNORECASE)
    if blocks:
        best = max(blocks, key=len)
        return best.strip()

    anchors = ["#include", "void setup", "int main", "const int", "class "]
    lower_text = text.lower()
    idx = len(text)
    for anchor in anchors:
        position = lower_text.find(anchor.lower())
        if position != -1:
            idx = min(idx, position)
    candidate = text[idx:] if idx < len(text) else text
    return candidate.strip()


def build_prompt(task: dict, prompt_style: str, is_repair: bool, previous_code: str, compile_error: str) -> str:
    if prompt_style == "structured":
        base = task["structured_prompt"]
    elif prompt_style == "simple":
        base = task["simple_prompt"]
    else:
        raise ValueError(f"Unsupported prompt style: {prompt_style}")

    if not is_repair:
        return base

    return (
        f"{base}\n\n"
        "The previous code failed to compile. Repair the code using the exact compiler errors below.\n"
        "Return only a complete Arduino .ino program in one fenced code block.\n\n"
        "Previous code:\n"
        "```cpp\n"
        f"{previous_code}\n"
        "```\n\n"
        "Compiler errors:\n"
        "```text\n"
        f"{compile_error}\n"
        "```\n"
    )


def call_openai(api_key: str, model: str, temperature: float, prompt: str, timeout_seconds: int) -> Tuple[str, float]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You generate compile-ready Arduino programs."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }

    started = time.time()
    response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    elapsed = time.time() - started
    if response.status_code >= 400:
        category, message, retryable = parse_openai_http_error(response)
        raise ApiRequestError(category, message, retryable)
    content = response.json()["choices"][0]["message"]["content"]
    return content, elapsed


def call_google(api_key: str, model: str, temperature: float, prompt: str, timeout_seconds: int) -> Tuple[str, float]:
    model_id = model.strip()
    if model_id.startswith("models/"):
        model_id = model_id.split("models/", 1)[1]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }

    started = time.time()
    response = requests.post(url, json=payload, timeout=timeout_seconds)
    elapsed = time.time() - started
    if response.status_code >= 400:
        category, message, retryable = parse_google_http_error(response)
        raise ApiRequestError(category, message, retryable)

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Google API returned no candidates: {data}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [part.get("text", "") for part in parts if "text" in part]
    content = "\n".join(text_parts).strip()
    if not content:
        raise RuntimeError(f"Google API returned empty text content: {data}")
    return content, elapsed


def call_model_with_timeout_retry(
    provider: ProviderConfig,
    prompt: str,
    request_timeout_seconds: int,
    reset_retry_count: int,
) -> Tuple[str, float, str, str]:
    provider_lower = provider.name.lower()
    api_key = ""

    if provider_lower == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is missing.")
        call_fn = call_openai
    elif provider_lower == "google":
        api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY environment variable is missing.")
        call_fn = call_google
    else:
        raise ValueError(f"Unsupported provider: {provider.name}")

    last_error = ""
    for attempt in range(reset_retry_count + 1):
        try:
            text, latency = call_fn(api_key, provider.model, provider.temperature, prompt, request_timeout_seconds)
            return text, latency, "ok", ""
        except requests.Timeout as exc:
            last_error = f"timeout: {exc}"
            if attempt < reset_retry_count:
                time.sleep(min(2**attempt, 8))
                continue
            return "", float(request_timeout_seconds), "timeout", last_error
        except ApiRequestError as exc:
            last_error = sanitize_error_message(exc.message)
            if exc.retryable and attempt < reset_retry_count:
                time.sleep(min(2**attempt, 8))
                continue
            return "", 0.0, exc.category, last_error
        except Exception as exc:  # noqa: BLE001
            last_error = sanitize_error_message(str(exc))
            return "", 0.0, "error", last_error
    return "", 0.0, "error", last_error


def write_sketch(sketch_dir: Path, sketch_name: str, code: str) -> Path:
    ensure_dir(sketch_dir)
    sketch_path = sketch_dir / f"{sketch_name}.ino"
    sketch_path.write_text(code, encoding="utf-8")
    return sketch_path


def compile_sketch(sketch_dir: Path, fqbn: str, timeout_seconds: int) -> Tuple[bool, str, float]:
    command = ["arduino-cli", "compile", "--fqbn", fqbn, str(sketch_dir)]
    started = time.time()
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
    elapsed = time.time() - started
    combined_log = f"{result.stdout}\n{result.stderr}".strip()
    return result.returncode == 0, combined_log, elapsed


def deploy_stub(sketch_dir: Path, fqbn: str, port: str) -> Dict[str, str]:
    return {
        "deploy_status": "skipped",
        "deploy_message": (
            "Deployment intentionally skipped in compile-only mode. "
            "Future implementation should call: arduino-cli upload -p <port> --fqbn <fqbn> <sketch_dir>."
        ),
        "port": port,
        "fqbn": fqbn,
        "sketch_dir": str(sketch_dir),
    }


def append_rows_to_csv(csv_path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary_csv(summary_csv: Path, rows: List[dict]) -> None:
    grouped: Dict[Tuple[str, str, str, str], dict] = {}

    for row in rows:
        key = (row["provider"], row["model"], row["task_name"], row["prompt_style"])
        grouped.setdefault(
            key,
            {
                "provider": row["provider"],
                "model": row["model"],
                "task_name": row["task_name"],
                "prompt_style": row["prompt_style"],
                "runs": 0,
                "compiled_runs": 0,
                "model_timeout_runs": 0,
                "model_quota_exhausted_runs": 0,
                "model_rate_limited_runs": 0,
                "avg_iterations_used": 0.0,
                "avg_model_latency_s": 0.0,
                "avg_compile_latency_s": 0.0,
            },
        )

    for metrics in grouped.values():
        relevant = [
            r
            for r in rows
            if r["provider"] == metrics["provider"]
            and r["model"] == metrics["model"]
            and r["task_name"] == metrics["task_name"]
            and r["prompt_style"] == metrics["prompt_style"]
            and r["is_run_terminal_row"] == "1"
        ]
        if not relevant:
            continue

        metrics["runs"] = len(relevant)
        metrics["compiled_runs"] = sum(1 for r in relevant if r["run_compiled"] == "1")
        metrics["model_timeout_runs"] = sum(1 for r in relevant if r["stop_reason"] == "model_timeout")
        metrics["model_quota_exhausted_runs"] = sum(
            1 for r in relevant if r["stop_reason"] == "model_quota_exhausted"
        )
        metrics["model_rate_limited_runs"] = sum(1 for r in relevant if r["stop_reason"] == "model_rate_limited")
        metrics["avg_iterations_used"] = sum(float(r["iterations_used"]) for r in relevant) / len(relevant)
        metrics["avg_model_latency_s"] = sum(float(r["model_latency_s"]) for r in relevant) / len(relevant)
        metrics["avg_compile_latency_s"] = sum(float(r["compile_latency_s"]) for r in relevant) / len(relevant)

    fieldnames = [
        "provider",
        "model",
        "task_name",
        "prompt_style",
        "runs",
        "compiled_runs",
        "model_timeout_runs",
        "model_quota_exhausted_runs",
        "model_rate_limited_runs",
        "avg_iterations_used",
        "avg_model_latency_s",
        "avg_compile_latency_s",
    ]
    with summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in grouped.values():
            writer.writerow(item)


def format_human_timestamp(dt: datetime) -> str:
    return dt.strftime("%A %B %d %Y at %I:%M%p")


def update_run_history(results_root: Path, run_root: Path, details_csv: Path, summary_csv: Path, completed_at: datetime) -> None:
    history_path = results_root / "results.json"
    ensure_dir(results_root)

    history: dict
    if history_path.exists():
        try:
            with history_path.open("r", encoding="utf-8") as file:
                loaded = json.load(file)
            history = loaded if isinstance(loaded, dict) else {}
        except (json.JSONDecodeError, OSError):
            history = {}
    else:
        history = {}

    existing_runs = history.get("runs", [])
    if not isinstance(existing_runs, list):
        existing_runs = []

    new_entry = {
        "run_number": int(history.get("total_runs", 0)) + 1,
        "timestamp": completed_at.isoformat(timespec="seconds"),
        "timestamp_human": format_human_timestamp(completed_at),
        "run_root": str(run_root),
        "results_detailed_csv": str(details_csv),
        "results_summary_csv": str(summary_csv),
    }
    existing_runs.insert(0, new_entry)

    history_doc = {
        "total_runs": len(existing_runs),
        "last_updated": completed_at.isoformat(timespec="seconds"),
        "last_updated_human": format_human_timestamp(completed_at),
        "runs": existing_runs,
    }
    history_path.write_text(json.dumps(history_doc, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile-first LLM embedded testbench runner")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to run config JSON")
    parser.add_argument("--prompts", default=DEFAULT_PROMPTS_PATH, help="Path to prompts JSON")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    prompts = load_json(Path(args.prompts))

    providers = [ProviderConfig(**provider) for provider in config["providers"]]
    prompt_styles: List[str] = config["prompt_styles"]
    repetitions = int(config["repetitions"])
    max_debug_retries = int(config["max_debug_retries"])
    request_timeout_seconds = int(config["request_timeout_seconds"])
    request_reset_retry_count = int(config["request_reset_retry_count"])
    compile_timeout_seconds = int(config["compile_timeout_seconds"])

    run_root = Path(config.get("output_root", "runs")) / datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    programs_root = run_root / "programs"
    logs_root = run_root / "compile_logs"
    ensure_dir(programs_root)
    ensure_dir(logs_root)

    rows: List[dict] = []

    print(f"Run output: {run_root}")
    print("Compile-only mode active: deployment is stubbed and hardware execution is skipped.")

    for provider in providers:
        for task in prompts["tasks"]:
            task_name = task["name"]
            for prompt_style in prompt_styles:
                for repetition_idx in range(repetitions):
                    run_id = (
                        f"{sanitize_name(provider.name)}__{sanitize_name(provider.model)}__"
                        f"{sanitize_name(task_name)}__{sanitize_name(prompt_style)}__r{repetition_idx + 1}"
                    )
                    run_start = time.time()
                    print(f"Starting {run_id}")

                    run_compiled = False
                    stop_reason = "exhausted_retries"
                    total_model_latency = 0.0
                    total_compile_latency = 0.0
                    iterations_used = 0
                    previous_code = ""
                    previous_compile_error = ""

                    for iteration in range(max_debug_retries + 1):
                        iterations_used = iteration + 1
                        is_repair = iteration > 0
                        prompt = build_prompt(task, prompt_style, is_repair, previous_code, previous_compile_error)

                        model_text, model_latency, request_status, request_error = call_model_with_timeout_retry(
                            provider,
                            prompt,
                            request_timeout_seconds,
                            request_reset_retry_count,
                        )
                        total_model_latency += model_latency

                        if request_status != "ok":
                            if request_status == "timeout":
                                stop_reason = "model_timeout"
                            elif request_status == "quota_exhausted":
                                stop_reason = "model_quota_exhausted"
                            elif request_status == "rate_limited":
                                stop_reason = "model_rate_limited"
                            else:
                                stop_reason = "model_error"
                            row = {
                                "timestamp": datetime.now().isoformat(timespec="seconds"),
                                "run_id": run_id,
                                "provider": provider.name,
                                "model": provider.model,
                                "task_name": task_name,
                                "prompt_style": prompt_style,
                                "repetition": str(repetition_idx + 1),
                                "iteration": str(iteration),
                                "is_repair": "1" if is_repair else "0",
                                "request_status": request_status,
                                "request_error": request_error,
                                "model_latency_s": f"{model_latency:.4f}",
                                "compile_status": "not_run",
                                "compile_latency_s": "0.0000",
                                "compile_log_path": "",
                                "compiled_this_iteration": "0",
                                "run_compiled": "0",
                                "iterations_used": str(iterations_used),
                                "stop_reason": stop_reason,
                                "total_elapsed_s": f"{time.time() - run_start:.4f}",
                                "prompt_chars": str(len(prompt)),
                                "model_output_chars": "0",
                                "is_run_terminal_row": "0",
                            }
                            rows.append(row)
                            break

                        code = extract_code(model_text)
                        previous_code = code
                        sketch_name = sanitize_name(task_name)
                        sketch_dir = programs_root / run_id / f"iter_{iteration}"
                        sketch_path = write_sketch(sketch_dir, sketch_name, code)

                        compile_ok, compile_log, compile_latency = compile_sketch(
                            sketch_dir,
                            config["arduino"]["fqbn"],
                            compile_timeout_seconds,
                        )
                        total_compile_latency += compile_latency

                        compile_log_path = logs_root / f"{run_id}__iter_{iteration}.log"
                        compile_log_path.write_text(compile_log, encoding="utf-8")

                        if compile_ok:
                            run_compiled = True
                            stop_reason = "compiled"
                        else:
                            previous_compile_error = compile_log[-6000:]

                        row = {
                            "timestamp": datetime.now().isoformat(timespec="seconds"),
                            "run_id": run_id,
                            "provider": provider.name,
                            "model": provider.model,
                            "task_name": task_name,
                            "prompt_style": prompt_style,
                            "repetition": str(repetition_idx + 1),
                            "iteration": str(iteration),
                            "is_repair": "1" if is_repair else "0",
                            "request_status": "ok",
                            "request_error": "",
                            "model_latency_s": f"{model_latency:.4f}",
                            "compile_status": "compiled" if compile_ok else "failed",
                            "compile_latency_s": f"{compile_latency:.4f}",
                            "compile_log_path": str(compile_log_path),
                            "compiled_this_iteration": "1" if compile_ok else "0",
                            "run_compiled": "0",
                            "iterations_used": str(iterations_used),
                            "stop_reason": "",
                            "total_elapsed_s": f"{time.time() - run_start:.4f}",
                            "prompt_chars": str(len(prompt)),
                            "model_output_chars": str(len(model_text)),
                            "is_run_terminal_row": "0",
                        }
                        rows.append(row)

                        if compile_ok:
                            deploy_info = deploy_stub(
                                sketch_dir,
                                config["arduino"]["fqbn"],
                                config["arduino"].get("port", ""),
                            )
                            deploy_stub_path = logs_root / f"{run_id}__deploy_stub.json"
                            deploy_stub_path.write_text(json.dumps(deploy_info, indent=2), encoding="utf-8")
                            break

                    terminal_row = {
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "run_id": run_id,
                        "provider": provider.name,
                        "model": provider.model,
                        "task_name": task_name,
                        "prompt_style": prompt_style,
                        "repetition": str(repetition_idx + 1),
                        "iteration": "-1",
                        "is_repair": "0",
                        "request_status": "summary",
                        "request_error": "",
                        "model_latency_s": f"{total_model_latency:.4f}",
                        "compile_status": "compiled" if run_compiled else "not_compiled",
                        "compile_latency_s": f"{total_compile_latency:.4f}",
                        "compile_log_path": "",
                        "compiled_this_iteration": "0",
                        "run_compiled": "1" if run_compiled else "0",
                        "iterations_used": str(iterations_used),
                        "stop_reason": stop_reason,
                        "total_elapsed_s": f"{time.time() - run_start:.4f}",
                        "prompt_chars": "0",
                        "model_output_chars": "0",
                        "is_run_terminal_row": "1",
                    }
                    rows.append(terminal_row)

    details_csv = run_root / "results_detailed.csv"
    summary_csv = run_root / "results_summary.csv"

    fieldnames = [
        "timestamp",
        "run_id",
        "provider",
        "model",
        "task_name",
        "prompt_style",
        "repetition",
        "iteration",
        "is_repair",
        "request_status",
        "request_error",
        "model_latency_s",
        "compile_status",
        "compile_latency_s",
        "compile_log_path",
        "compiled_this_iteration",
        "run_compiled",
        "iterations_used",
        "stop_reason",
        "total_elapsed_s",
        "prompt_chars",
        "model_output_chars",
        "is_run_terminal_row",
    ]

    append_rows_to_csv(details_csv, rows, fieldnames)
    write_summary_csv(summary_csv, rows)

    completed_at = datetime.now()
    update_run_history(run_root.parent, run_root, details_csv, summary_csv, completed_at)

    print(f"Detailed CSV: {details_csv}")
    print(f"Summary CSV: {summary_csv}")


if __name__ == "__main__":
    main()
        

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import { spawn } from 'child_process';

export function activate(context: vscode.ExtensionContext) {
	const provider = new TestbenchViewProvider(context.extensionUri);
	context.subscriptions.push(
		vscode.window.registerWebviewViewProvider('arduinoTestbench.panel', provider)
	);
}

export function deactivate() { }

class TestbenchViewProvider implements vscode.WebviewViewProvider {
	private _view?: vscode.WebviewView;

	constructor(private readonly _extensionUri: vscode.Uri) { }

	resolveWebviewView(webviewView: vscode.WebviewView) {
		this._view = webviewView;
		webviewView.webview.options = { enableScripts: true };

		const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '';
		const tasks = this._loadTasks(workspacePath);
		const providerProfiles = this._loadProviderProfiles(workspacePath);

		webviewView.webview.html = getWebviewContent(tasks, providerProfiles);

		webviewView.webview.onDidReceiveMessage(message => {
			switch (message.command) {
				case 'run':
					this._runExperiment(webviewView, workspacePath, message.config);
					break;
				case 'copyCode':
					this._copyLatestCode(workspacePath);
					break;
				case 'openResults':
					vscode.commands.executeCommand('revealFileInOS',
						vscode.Uri.file(path.join(workspacePath, 'results')));
					break;
			}
		});
	}

	private _loadTasks(workspacePath: string): string[] {
		try {
			const raw = fs.readFileSync(path.join(workspacePath, 'llm_prompts.json'), 'utf-8');
			return JSON.parse(raw).tasks?.map((t: { name: string }) => t.name) ?? [];
		} catch {
			return ['(open your testbench project folder)'];
		}
	}

	private _loadProviderProfiles(workspacePath: string): Record<string, { name: string; model: string }[]> {
		try {
			const raw = fs.readFileSync(path.join(workspacePath, 'run_config.json'), 'utf-8');
			const config = JSON.parse(raw);
			// provider_profiles: { default: [...], cloud: [...], local: [...], all: [...] }
			const profiles = config.provider_profiles ?? {};
			const result: Record<string, { name: string; model: string }[]> = {};
			for (const [profileName, providers] of Object.entries(profiles)) {
				result[profileName] = (providers as any[]).map(p => ({
					name: p.name,
					model: p.model
				}));
			}
			return result;
		} catch {
			return {
				default: [{ name: 'OpenAI', model: 'gpt-4o' }],
				local: [{ name: 'Ollama', model: 'llama3' }]
			};
		}
	}

	private _runExperiment(webviewView: vscode.WebviewView, workspacePath: string, config: any) {
		const post = (msg: object) => webviewView.webview.postMessage(msg);

		if (!workspacePath) {
			post({ command: 'log', text: 'ERROR: No workspace folder open.' });
			post({ command: 'done', exitCode: 1, latestCode: '' });
			return;
		}

		const testbenchPath = path.join(workspacePath, 'testbench.py');
		if (!fs.existsSync(testbenchPath)) {
			post({ command: 'log', text: `ERROR: testbench.py not found in ${workspacePath}` });
			post({ command: 'done', exitCode: 1, latestCode: '' });
			return;
		}

		// --- Read real config files ---
		let baseConfig: any = {};
		let allTasks: any[] = [];

		try {
			baseConfig = JSON.parse(fs.readFileSync(path.join(workspacePath, 'run_config.json'), 'utf-8'));
		} catch {
			post({ command: 'log', text: 'ERROR: Could not read run_config.json' });
			post({ command: 'done', exitCode: 1, latestCode: '' });
			return;
		}

		try {
			const raw = fs.readFileSync(path.join(workspacePath, 'llm_prompts.json'), 'utf-8');
			allTasks = JSON.parse(raw).tasks ?? [];
		} catch {
			post({ command: 'log', text: 'ERROR: Could not read llm_prompts.json' });
			post({ command: 'done', exitCode: 1, latestCode: '' });
			return;
		}

		// --- Back up originals ---
		const configPath = path.join(workspacePath, 'run_config.json');
		const promptsPath = path.join(workspacePath, 'llm_prompts.json');
		const configBackup = JSON.stringify(baseConfig, null, 2);
		const promptsBackup = JSON.stringify({ tasks: allTasks }, null, 2);

		// --- Build overridden config ---
		const overriddenConfig = {
			...baseConfig,
			max_debug_retries: config.retries,
			repetitions: config.reps,
			prompt_styles: config.style === 'both' ? ['simple', 'structured']
				: config.style === 'simple' ? ['simple']
					: ['structured'],
			arduino: {
				...(baseConfig.arduino ?? {}),
				fqbn: config.fqbn
			}
		};

		// Filter prompts to selected task only
		const filteredTasks = allTasks.filter((t: any) => t.name === config.task);

		// --- Write overrides in place ---
		try {
			fs.writeFileSync(configPath, JSON.stringify(overriddenConfig, null, 2));
			fs.writeFileSync(promptsPath, JSON.stringify({ tasks: filteredTasks }, null, 2));
		} catch (e: any) {
			post({ command: 'log', text: `ERROR writing config overrides: ${e.message}` });
			post({ command: 'done', exitCode: 1, latestCode: '' });
			return;
		}

		// --- Restore helper (always called after process exits) ---
		const restore = () => {
			try { fs.writeFileSync(configPath, configBackup); } catch { }
			try { fs.writeFileSync(promptsPath, promptsBackup); } catch { }
		};

		// --- Resolve mode flag ---
		const modeArgMap: Record<string, string> = {
			cloud: '--cloud',
			local: '--local',
			all: '--all',
			default: ''
		};
		const modeArg = modeArgMap[config.mode] ?? '';

		// --- Resolve venv Python ---
		const isWindows = process.platform === 'win32';
		const pythonPath = isWindows
			? path.join(workspacePath, '.venv', 'Scripts', 'python.exe')
			: path.join(workspacePath, '.venv', 'bin', 'python');

		if (!fs.existsSync(pythonPath)) {
			restore();
			post({ command: 'log', text: `ERROR: venv not found at ${pythonPath}` });
			post({ command: 'log', text: 'Run: python -m venv .venv && .venv/bin/pip install -r requirements.txt' });
			post({ command: 'done', exitCode: 1, latestCode: '' });
			return;
		}

		const spawnArgs = ['-u', 'testbench.py', ...(modeArg ? [modeArg] : [])];

		post({ command: 'log', text: `Mode: ${config.mode}` });
		post({ command: 'log', text: `Task: ${config.task}` });
		post({ command: 'log', text: `Style: ${config.style}` });

		const python = spawn(pythonPath, spawnArgs, {
			cwd: workspacePath,
			env: { ...process.env }
		});

		python.on('error', (err: Error) => {
			restore();
			post({ command: 'log', text: `ERROR spawning Python: ${err.message}` });
			post({ command: 'done', exitCode: 1, latestCode: '' });
		});

		python.stdout.on('data', (data: Buffer) => {
			data.toString().split('\n')
				.filter((l: string) => l.trim())
				.forEach((line: string) => post({ command: 'log', text: line }));
		});

		python.stderr.on('data', (data: Buffer) => {
			data.toString().split('\n')
				.filter((l: string) => l.trim())
				.forEach((line: string) => post({ command: 'log', text: line }));
		});

		python.on('close', (code: number) => {
			restore();  // always restore originals when done
			const latestCode = this._findLatestSketch(workspacePath);
			post({ command: 'done', exitCode: code, latestCode });
		});
	}

	private _findLatestSketch(workspacePath: string): string {
		try {
			// Output root is now "results" not "runs"
			const resultsDir = path.join(workspacePath, 'results');
			if (!fs.existsSync(resultsDir)) { return ''; }

			const runDirs = fs.readdirSync(resultsDir)
				.map(name => path.join(resultsDir, name))
				.filter(p => fs.statSync(p).isDirectory())
				.sort().reverse();

			if (!runDirs.length) { return ''; }

			const programsDir = path.join(runDirs[0], 'programs');
			if (!fs.existsSync(programsDir)) { return ''; }

			const inoFiles: string[] = [];
			const walk = (dir: string) => {
				fs.readdirSync(dir).forEach(f => {
					const full = path.join(dir, f);
					if (fs.statSync(full).isDirectory()) { walk(full); }
					else if (f.endsWith('.ino')) { inoFiles.push(full); }
				});
			};
			walk(programsDir);

			if (!inoFiles.length) { return ''; }

			inoFiles.sort((a, b) => {
				const iterA = parseInt(a.match(/iter_(\d+)/)?.[1] ?? '0');
				const iterB = parseInt(b.match(/iter_(\d+)/)?.[1] ?? '0');
				return iterB - iterA;
			});

			return fs.readFileSync(inoFiles[0], 'utf-8');
		} catch {
			return '';
		}
	}

	private _copyLatestCode(workspacePath: string) {
		const code = this._findLatestSketch(workspacePath);
		if (code) {
			vscode.env.clipboard.writeText(code);
			vscode.window.showInformationMessage('Arduino sketch copied to clipboard!');
		} else {
			vscode.window.showWarningMessage('No generated sketch found yet.');
		}
	}
}

function getWebviewContent(
	tasks: string[],
	providerProfiles: Record<string, { name: string; model: string }[]>
): string {
	const taskOptions = tasks.map(t =>
		`<option value="${t}">${t}</option>`
	).join('\n');

	// Build a summary of what each mode runs, for display in the UI
	const modeDescriptions: Record<string, string> = {};
	for (const [mode, providers] of Object.entries(providerProfiles)) {
		modeDescriptions[mode] = providers.map(p => `${p.name} (${p.model})`).join(', ');
	}

	// Serialize for use in the webview JS
	const modeDescJson = JSON.stringify(modeDescriptions);
	const profilesJson = JSON.stringify(providerProfiles);

	return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: var(--vscode-font-family);
    font-size: 12px;
    color: var(--vscode-foreground);
    background: transparent;
  }
  .section {
    padding: 10px 12px;
    border-bottom: 1px solid var(--vscode-panel-border);
  }
  .label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--vscode-descriptionForeground);
    margin-bottom: 5px;
    font-weight: 600;
  }
  select, input[type="number"], input[type="text"] {
    width: 100%;
    background: var(--vscode-input-background);
    color: var(--vscode-input-foreground);
    border: 1px solid var(--vscode-input-border);
    border-radius: 3px;
    padding: 4px 6px;
    font-size: 12px;
    font-family: inherit;
  }
  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .radio-group { display: flex; gap: 10px; flex-wrap: wrap; padding: 2px 0; }
  .radio-group label { display: flex; align-items: center; gap: 4px; cursor: pointer; }
  .mode-desc {
    margin-top: 5px;
    font-size: 10px;
    color: var(--vscode-descriptionForeground);
    font-style: italic;
    min-height: 14px;
  }
  .btn {
    width: 100%; padding: 7px;
    border-radius: 3px; font-size: 12px; font-weight: 600;
    cursor: pointer; display: flex; align-items: center;
    justify-content: center; gap: 6px; border: none;
  }
  .btn-primary {
    background: var(--vscode-button-background);
    color: var(--vscode-button-foreground);
  }
  .btn-primary:hover { background: var(--vscode-button-hoverBackground); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary {
    background: transparent;
    color: var(--vscode-foreground);
    border: 1px solid var(--vscode-panel-border) !important;
    margin-top: 6px;
  }
  .btn-secondary:hover { background: var(--vscode-list-hoverBackground); }
  .btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }
  .play { width:0; height:0; border-top:5px solid transparent; border-bottom:5px solid transparent; border-left:8px solid var(--vscode-button-foreground); }
  .log-area {
    background: var(--vscode-terminal-background, var(--vscode-editor-background));
    border: 1px solid var(--vscode-panel-border);
    border-radius: 3px; padding: 7px 9px;
    font-family: var(--vscode-editor-font-family);
    font-size: 11px; line-height: 1.6;
    min-height: 90px; max-height: 200px; overflow-y: auto;
  }
  .log-default { color: var(--vscode-terminal-foreground, var(--vscode-foreground)); }
  .log-ok    { color: var(--vscode-terminal-ansiGreen); }
  .log-err   { color: var(--vscode-terminal-ansiRed); }
  .log-warn  { color: var(--vscode-terminal-ansiYellow); }
  .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .metric { background: var(--vscode-editor-inactiveSelectionBackground); border-radius: 3px; padding: 7px 9px; }
  .metric-val { font-size: 18px; font-weight: 600; }
  .metric-lbl { font-size: 10px; color: var(--vscode-descriptionForeground); margin-top: 1px; }
  .open-btn {
    width: 100%; margin-top: 8px; padding: 5px;
    background: transparent; border: 1px solid var(--vscode-panel-border);
    border-radius: 3px; font-size: 11px;
    color: var(--vscode-descriptionForeground); cursor: pointer;
  }
  .open-btn:hover { background: var(--vscode-list-hoverBackground); }
  .badge { font-size: 10px; padding: 1px 7px; border-radius: 99px; font-weight: 600; }
  .badge-running { background: var(--vscode-terminal-ansiYellow); color: #000; }
  .badge-done    { background: var(--vscode-terminal-ansiGreen); color: #000; }
  .badge-error   { background: var(--vscode-terminal-ansiRed); color: #fff; }
  .section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; }
</style>
</head>
<body>

<div class="section">
  <div class="label">Task</div>
  <select id="task">${taskOptions}</select>
</div>

<div class="section">
  <div class="label">Prompt style</div>
  <div class="radio-group">
    <label><input type="radio" name="style" value="simple" checked> Simple</label>
    <label><input type="radio" name="style" value="structured"> Structured</label>
    <label><input type="radio" name="style" value="both"> Both</label>
  </div>
</div>

<div class="section">
  <div class="label">Provider mode</div>
  <div class="radio-group" id="modeGroup">
    <label><input type="radio" name="mode" value="default" checked> Default</label>
    <label><input type="radio" name="mode" value="cloud"> Cloud</label>
    <label><input type="radio" name="mode" value="local"> Local</label>
    <label><input type="radio" name="mode" value="all"> All</label>
  </div>
  <div class="mode-desc" id="modeDesc"></div>
</div>

<div class="section">
  <div class="row2">
    <div><div class="label">Retries</div><input type="number" id="retries" value="5" min="1" max="10"></div>
    <div><div class="label">Repetitions</div><input type="number" id="reps" value="1" min="1" max="20"></div>
  </div>
  <div style="margin-top:8px;">
    <div class="label">Board FQBN</div>
    <input type="text" id="fqbn" value="arduino:avr:mega">
  </div>
</div>

<div class="section">
  <button class="btn btn-primary" id="runBtn" onclick="startRun()">
    <div class="play"></div> Run experiment
  </button>
  <button class="btn btn-secondary" id="copyBtn" onclick="copyCode()" disabled>
    Copy generated sketch
  </button>
</div>

<div class="section" id="logSection" style="display:none;">
  <div class="section-header">
    <div class="label" style="margin:0;">Log</div>
    <span class="badge badge-running" id="statusBadge">running</span>
  </div>
  <div class="log-area" id="logArea"></div>
</div>

<div class="section" id="resultsSection" style="display:none;">
  <div class="section-header">
    <div class="label" style="margin:0;">Results</div>
    <span class="badge badge-done">done</span>
  </div>
  <div class="metric-grid">
    <div class="metric"><div class="metric-val" id="mIter">—</div><div class="metric-lbl">Iterations used</div></div>
    <div class="metric"><div class="metric-val" id="mTotal">—</div><div class="metric-lbl">Total time</div></div>
    <div class="metric"><div class="metric-val" id="mCompile">—</div><div class="metric-lbl">Compile time</div></div>
    <div class="metric"><div class="metric-val" id="mPass">—</div><div class="metric-lbl">Pass rate</div></div>
  </div>
  <button class="open-btn" onclick="openResults()">Open results folder</button>
</div>

<script>
  const vscode = acquireVsCodeApi();
  const logArea = document.getElementById('logArea');
  const modeDescs = ${modeDescJson};

  // Show provider summary when mode changes
  function updateModeDesc() {
    const mode = document.querySelector('input[name=mode]:checked').value;
    document.getElementById('modeDesc').textContent = modeDescs[mode] ?? '';
  }
  document.querySelectorAll('input[name=mode]').forEach(r =>
    r.addEventListener('change', updateModeDesc)
  );
  updateModeDesc();

  let startTime = 0;
  let compileOk = false;
  let iterCount = 0;

  function startRun() {
    logArea.innerHTML = '';
    document.getElementById('logSection').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('statusBadge').textContent = 'running';
    document.getElementById('statusBadge').className = 'badge badge-running';
    document.getElementById('runBtn').disabled = true;
    document.getElementById('copyBtn').disabled = true;
    startTime = Date.now();
    compileOk = false;
    iterCount = 0;

    vscode.postMessage({
      command: 'run',
      config: {
        task:    document.getElementById('task').value,
        style:   document.querySelector('input[name=style]:checked').value,
        mode:    document.querySelector('input[name=mode]:checked').value,
        retries: parseInt(document.getElementById('retries').value),
        reps:    parseInt(document.getElementById('reps').value),
        fqbn:    document.getElementById('fqbn').value,
      }
    });
  }

  function appendLog(text) {
    const line = document.createElement('div');
    const t = text.toLowerCase();
    if (t.includes('success') || t.includes('compiled') || t.includes('done') || t.includes('detailed csv')) {
      line.className = 'log-default log-ok';
      if (t.includes('compiled') || t.includes('success')) { compileOk = true; }
    } else if (t.includes('error') || t.includes('fail')) {
      line.className = 'log-default log-err';
    } else if (t.includes('repair') || t.includes('retry') || t.includes('starting') || t.includes('warning')) {
      line.className = 'log-default log-warn';
    } else {
      line.className = 'log-default';
    }
    if (t.includes('starting ')) { iterCount++; }
    line.textContent = '> ' + text;
    logArea.appendChild(line);
    logArea.scrollTop = logArea.scrollHeight;
  }

  function copyCode()    { vscode.postMessage({ command: 'copyCode' }); }
  function openResults() { vscode.postMessage({ command: 'openResults' }); }

  window.addEventListener('message', event => {
    const msg = event.data;
    if (msg.command === 'log') {
      appendLog(msg.text);
    } else if (msg.command === 'done') {
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      const ok = msg.exitCode === 0;
      document.getElementById('statusBadge').textContent = ok ? 'done' : 'error';
      document.getElementById('statusBadge').className = 'badge ' + (ok ? 'badge-done' : 'badge-error');
      document.getElementById('runBtn').disabled = false;
      if (msg.latestCode) {
        document.getElementById('copyBtn').disabled = false;
      }
      document.getElementById('resultsSection').style.display = 'block';
      document.getElementById('mIter').textContent = iterCount || '—';
      document.getElementById('mTotal').textContent = elapsed + 's';
      document.getElementById('mCompile').textContent = '—';
      document.getElementById('mPass').textContent = compileOk ? '100%' : '0%';
    }
  });
</script>
</body>
</html>`;
}
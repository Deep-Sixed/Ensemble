import * as vscode from "vscode";

type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

type EnsembleConfig = {
  baseUrl: string;
  model: string;
  apiKey: string;
  maxTokens: number;
  temperature: number;
};

const SYSTEM_PROMPT = [
  "You are Ensemble, a technical local AI assistant for homelab, coding, Docker, Linux, model serving, MCP, LSP, indexing, and repo automation.",
  "Use direct technical answers. Avoid emojis, corporate assistant tone, personhood claims, and exaggerated praise.",
  "Default model is qwen2.5-coder-7b-instruct-q4_k_m. Qwen3 4B is fast/general. Qwen3.6 35B is explicit reasoning mode only."
].join("\n");

export function activate(context: vscode.ExtensionContext): void {
  const chatProvider = new EnsembleChatProvider(context.extensionUri);
  const statusBar = new EnsembleStatusBar();

  context.subscriptions.push(
    statusBar,
    vscode.window.registerWebviewViewProvider("ensemble.chat", chatProvider),
    vscode.commands.registerCommand("ensemble.checkHealth", () => checkHealth(statusBar)),
    vscode.commands.registerCommand("ensemble.askSelection", askSelection),
    vscode.commands.registerCommand("ensemble.askCurrentFile", askCurrentFile),
    vscode.commands.registerCommand("ensemble.reviewWorkspace", reviewWorkspace),
    vscode.commands.registerCommand("ensemble.applyPatch", applyPatch),
    vscode.commands.registerCommand("ensemble.openSettings", openSettings)
  );

  statusBar.check();
}

export function deactivate(): void {
  return;
}

async function checkHealth(statusBar?: EnsembleStatusBar): Promise<void> {
  statusBar?.setChecking();
  const config = getConfig();
  try {
    const models = await getModels(config);
    const active = models.map((model) => model.id ?? model.name ?? String(model)).join(", ");
    statusBar?.setHealthy(displayModelName(active));
    vscode.window.showInformationMessage(`Ensemble healthy: ${active}`);
  } catch (error) {
    statusBar?.setOffline();
    vscode.window.showErrorMessage(`Ensemble health check failed: ${formatError(error)}`);
  }
}

async function askSelection(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.selection.isEmpty) {
    vscode.window.showWarningMessage("Select code or text first.");
    return;
  }

  const selected = editor.document.getText(editor.selection);
  const prompt = await vscode.window.showInputBox({
    prompt: "Ask Ensemble about the selected text",
    value: "Explain this selection and point out risks."
  });
  if (!prompt) {
    return;
  }

  await askAndShow(`${prompt}\n\nSelection:\n\`\`\`\n${selected}\n\`\`\``);
}

async function askCurrentFile(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("Open a file first.");
    return;
  }

  const prompt = await vscode.window.showInputBox({
    prompt: "Ask Ensemble about the current file",
    value: "Summarize this file and identify likely maintenance risks."
  });
  if (!prompt) {
    return;
  }

  const document = editor.document;
  await askAndShow(
    [
      prompt,
      "",
      `File: ${document.uri.fsPath}`,
      "```",
      document.getText(),
      "```"
    ].join("\n")
  );
}

async function reviewWorkspace(): Promise<void> {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) {
    vscode.window.showWarningMessage("Open a workspace first.");
    return;
  }

  await askAndShow(
    [
      "Review this workspace at a high level.",
      "Focus on architecture risks, verification gaps, and next commands to run.",
      `Workspace: ${root}`
    ].join("\n")
  );
}

async function applyPatch(): Promise<void> {
  vscode.window.showInformationMessage(
    "Patch application is not enabled in the extension MVP. Use Ensemble CLI checkpointed edits."
  );
}

async function openSettings(): Promise<void> {
  await vscode.commands.executeCommand(
    "workbench.action.openSettings",
    "@ext:ensemble.ensemble"
  );
}

async function askAndShow(prompt: string): Promise<void> {
  const config = getConfig();
  const title = "Ensemble";
  const panel = vscode.window.createOutputChannel(title);
  panel.show(true);
  panel.appendLine(`Model: ${config.model}`);
  panel.appendLine(`Endpoint: ${config.baseUrl}`);
  panel.appendLine("");
  panel.appendLine("Request:");
  panel.appendLine(prompt);
  panel.appendLine("");
  panel.appendLine("Response:");

  try {
    const result = await chat(config, [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: prompt }
    ]);
    panel.appendLine(result);
  } catch (error) {
    panel.appendLine(`Error: ${formatError(error)}`);
    vscode.window.showErrorMessage(`Ensemble request failed: ${formatError(error)}`);
  }
}

class EnsembleChatProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;

  constructor(private readonly extensionUri: vscode.Uri) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.extensionUri]
    };
    webviewView.webview.html = this.html(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (message: { type: string; text?: string }) => {
      if (message.type === "health") {
        await this.postHealth();
      }
      if (message.type === "ask" && message.text) {
        await this.postAnswer(message.text);
      }
    });
  }

  private async postHealth(): Promise<void> {
    const config = getConfig();
    try {
      const models = await getModels(config);
      this.post({
        type: "status",
        text: `Healthy. Models: ${models.map((model) => model.id ?? model.name).join(", ")}`
      });
    } catch (error) {
      this.post({ type: "status", text: `Health failed: ${formatError(error)}` });
    }
  }

  private async postAnswer(prompt: string): Promise<void> {
    const config = getConfig();
    this.post({ type: "status", text: "Sending request..." });
    try {
      const answer = await chat(config, [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: prompt }
      ]);
      this.post({ type: "answer", text: answer });
      this.post({ type: "status", text: `Ready. ${config.model}` });
    } catch (error) {
      this.post({ type: "status", text: `Request failed: ${formatError(error)}` });
    }
  }

  private post(message: Record<string, string>): void {
    this.view?.webview.postMessage(message);
  }

  private html(_webview: vscode.Webview): string {
    const nonce = String(Date.now());
    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { padding: 12px; color: var(--vscode-foreground); font-family: var(--vscode-font-family); }
    textarea { width: 100%; min-height: 120px; resize: vertical; color: var(--vscode-input-foreground); background: var(--vscode-input-background); border: 1px solid var(--vscode-input-border); padding: 8px; }
    button { margin-top: 8px; margin-right: 6px; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; border-top: 1px solid var(--vscode-panel-border); padding-top: 12px; }
    .status { color: var(--vscode-descriptionForeground); margin: 8px 0 12px; }
  </style>
</head>
<body>
  <h2>Ensemble</h2>
  <div class="status" id="status">Endpoint: 127.0.0.1:8090</div>
  <textarea id="prompt" placeholder="Ask Ensemble..."></textarea>
  <div>
    <button id="ask">Ask</button>
    <button id="health">Health</button>
  </div>
  <pre id="answer"></pre>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const status = document.getElementById("status");
    const answer = document.getElementById("answer");
    document.getElementById("ask").addEventListener("click", () => {
      const text = document.getElementById("prompt").value;
      vscode.postMessage({ type: "ask", text });
    });
    document.getElementById("health").addEventListener("click", () => {
      vscode.postMessage({ type: "health" });
    });
    window.addEventListener("message", (event) => {
      const message = event.data;
      if (message.type === "status") status.textContent = message.text;
      if (message.type === "answer") answer.textContent = message.text;
    });
  </script>
</body>
</html>`;
  }
}

class EnsembleStatusBar implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;
  private timer?: NodeJS.Timeout;

  constructor() {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    this.item.command = "ensemble.checkHealth";
    this.item.tooltip = "Ensemble health. Click to check backend status.";
    this.setChecking();
    this.item.show();

    this.timer = setInterval(() => {
      this.check();
    }, 60_000);
  }

  async check(): Promise<void> {
    this.setChecking();
    const config = getConfig();
    try {
      const models = await getModels(config);
      const active = models
        .map((model) => model.id ?? model.name ?? "")
        .filter((model) => typeof model === "string" && model.length > 0)
        .join(", ");
      this.setHealthy(displayModelName(active || config.model));
    } catch {
      this.setOffline();
    }
  }

  setChecking(): void {
    this.item.text = "$(sync~spin) Ensemble: Checking...";
    this.item.tooltip = "Checking Ensemble backend health...";
  }

  setHealthy(modelName: string): void {
    this.item.text = `$(circle-filled) Ensemble: ${modelName}`;
    this.item.tooltip = "Ensemble backend is healthy. Click to run health check.";
  }

  setOffline(): void {
    this.item.text = "$(warning) Ensemble: Offline";
    this.item.tooltip = "Ensemble backend is offline. Click to run health check.";
  }

  dispose(): void {
    if (this.timer) {
      clearInterval(this.timer);
    }
    this.item.dispose();
  }
}

function getConfig(): EnsembleConfig {
  const config = vscode.workspace.getConfiguration("ensemble");
  return {
    baseUrl: trimTrailingSlash(config.get("baseUrl", "http://127.0.0.1:8090/v1")),
    model: config.get("model", "qwen2.5-coder-7b-instruct-q4_k_m"),
    apiKey: config.get("apiKey", "ensemble"),
    maxTokens: config.get("maxTokens", 1024),
    temperature: config.get("temperature", 0.2)
  };
}

async function getModels(config: EnsembleConfig): Promise<Array<Record<string, unknown>>> {
  const response = await fetchJson(`${config.baseUrl}/models`, {
    method: "GET",
    headers: headers(config)
  });
  const data = response.data;
  return Array.isArray(data) ? data : [];
}

async function chat(config: EnsembleConfig, messages: ChatMessage[]): Promise<string> {
  const response = await fetchJson(`${config.baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      ...headers(config),
      "content-type": "application/json"
    },
    body: JSON.stringify({
      model: config.model,
      messages,
      max_tokens: config.maxTokens,
      temperature: config.temperature,
      stream: false
    })
  });

  const content = response.choices?.[0]?.message?.content;
  if (typeof content !== "string") {
    throw new Error("No message content returned");
  }
  return content;
}

async function fetchJson(url: string, init: RequestInit): Promise<any> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json();
}

function headers(config: EnsembleConfig): Record<string, string> {
  return {
    authorization: `Bearer ${config.apiKey}`
  };
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function displayModelName(model: string): string {
  if (model.includes("qwen2.5-coder")) {
    return "Qwen2.5 Coder";
  }
  if (model.includes("qwen3-4b-instruct")) {
    return "Qwen3 4B";
  }
  if (model.includes("qwen3.6-35b")) {
    return "Qwen3.6 35B";
  }
  return model || "Unknown";
}

function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

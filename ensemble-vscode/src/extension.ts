import { execFile } from "node:child_process";
import * as vscode from "vscode";

type ContextPacket = {
  task: string;
  files: { path: string }[];
  context: string;
  token_estimate: number;
  token_budget: number;
  truncated: boolean;
};

type EnsembleSettings = {
  cliPath: string;
  tokenBudget: number;
  semantic: boolean;
};

const MAX_OUTPUT_BYTES = 64 * 1024 * 1024;

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("ensemble.buildContext", buildContext),
  );
}

export function deactivate(): void {
  return;
}

async function buildContext(): Promise<void> {
  const folder = activeWorkspaceFolder();
  if (!folder) {
    vscode.window.showWarningMessage("Open a workspace folder first.");
    return;
  }

  const task = await vscode.window.showInputBox({
    prompt: "Task the context should support",
    placeHolder: "Fix authentication timeout handling",
    ignoreFocusOut: true,
  });
  if (!task?.trim()) {
    return;
  }

  let packet: ContextPacket;
  try {
    packet = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Ensemble: assembling context",
      },
      () => runEnsembleContext(task.trim(), folder.uri.fsPath, getSettings()),
    );
  } catch (error) {
    vscode.window.showErrorMessage(
      `Ensemble context failed: ${formatError(error)}`,
    );
    return;
  }

  const summary =
    `Ensemble: ${packet.files.length} file(s), ~${packet.token_estimate}/` +
    `${packet.token_budget} tokens${packet.truncated ? " (truncated)" : ""}`;
  const choice = await vscode.window.showInformationMessage(
    summary,
    "Copy Context",
    "Open Packet",
  );
  if (choice === "Copy Context") {
    await vscode.env.clipboard.writeText(packet.context);
  } else if (choice === "Open Packet") {
    const document = await vscode.workspace.openTextDocument({
      language: "json",
      content: JSON.stringify(packet, null, 2),
    });
    await vscode.window.showTextDocument(document, { preview: false });
  }
}

function runEnsembleContext(
  task: string,
  workspace: string,
  settings: EnsembleSettings,
): Promise<ContextPacket> {
  const args = ["context", "--token-budget", String(settings.tokenBudget)];
  if (!settings.semantic) {
    args.push("--no-semantic");
  }
  // "--" keeps a task that starts with "-" from being parsed as an option.
  args.push("--", task);

  return new Promise((resolve, reject) => {
    // execFile passes arguments directly; the task text never reaches a shell.
    execFile(
      settings.cliPath,
      args,
      {
        cwd: workspace,
        env: { ...process.env, ENSEMBLE_WORKSPACE: workspace },
        maxBuffer: MAX_OUTPUT_BYTES,
      },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(stderr.trim() || error.message));
          return;
        }
        try {
          resolve(JSON.parse(stdout) as ContextPacket);
        } catch (parseError) {
          reject(parseError);
        }
      },
    );
  });
}

function activeWorkspaceFolder(): vscode.WorkspaceFolder | undefined {
  const activeUri = vscode.window.activeTextEditor?.document.uri;
  if (activeUri) {
    const folder = vscode.workspace.getWorkspaceFolder(activeUri);
    if (folder) {
      return folder;
    }
  }
  return vscode.workspace.workspaceFolders?.[0];
}

function getSettings(): EnsembleSettings {
  const config = vscode.workspace.getConfiguration("ensemble");
  return {
    cliPath: config.get<string>("cliPath", "ensemble"),
    tokenBudget: config.get<number>("tokenBudget", 12000),
    semantic: config.get<boolean>("semantic", true),
  };
}

function formatError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

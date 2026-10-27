#!/usr/bin/env node

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const isWindows = process.platform === "win32";
const defaultPython = isWindows
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : path.join(root, ".venv", "bin", "python");
const python = process.env.VENV_PYTHON || defaultPython;

if (!existsSync(python)) {
  console.error(
    `Python virtual environment not found at ${python}. Run "pnpm run bootstrap" first.`,
  );
  process.exit(1);
}

const args = process.argv.slice(2);
const env = { ...process.env };
while (args[0] === "--env") {
  args.shift();
  const assignment = args.shift();
  const separator = assignment?.indexOf("=") ?? -1;
  if (!assignment || separator <= 0) {
    console.error('Usage: node scripts/python.mjs --env KEY=VALUE <python-args...>');
    process.exit(2);
  }
  env[assignment.slice(0, separator)] = assignment.slice(separator + 1);
}

env.PYTHONPATH = path.join(root, "apps", "api");
env.PYTHONUNBUFFERED = "1";
env.PYTHONNOUSERSITE = "1";
delete env.PYTHONHOME;

const child = spawn(python, args, {
  cwd: root,
  env,
  stdio: "inherit",
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    if (!child.killed) {
      child.kill(signal);
    }
  });
}

child.on("error", (error) => {
  console.error(`Failed to start ${python}: ${error.message}`);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (code !== null) {
    process.exit(code);
  }
  process.exit(signal === "SIGINT" ? 130 : 1);
});

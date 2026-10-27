#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const isWindows = process.platform === "win32";
const venvDir = path.join(root, ".venv");
const venvPython = isWindows
  ? path.join(venvDir, "Scripts", "python.exe")
  : path.join(venvDir, "bin", "python");
const pnpm = "pnpm";
const apiPath = path.join(root, "apps", "api");

function run(command, args, extraEnv = {}, options = {}) {
  const env = { ...process.env, ...extraEnv };
  if (options.isolatedPython) {
    env.PYTHONPATH = apiPath;
    env.PYTHONNOUSERSITE = "1";
    delete env.PYTHONHOME;
  }
  const result = spawnSync(command, args, {
    cwd: root,
    env,
    shell: options.shell ?? false,
    stdio: "inherit",
  });
  if (result.error) {
    throw new Error(`${command} failed to start: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} exited with status ${result.status}`);
  }
}

function runPython(args, extraEnv = {}) {
  run(venvPython, args, extraEnv, { isolatedPython: true });
}

function versionOf(command, prefix = []) {
  const result = spawnSync(command, [...prefix, "--version"], {
    cwd: root,
    encoding: "utf8",
  });
  if (result.error || result.status !== 0) {
    return null;
  }
  const output = `${result.stdout || ""}\n${result.stderr || ""}`;
  const match = output.match(/Python\s+(\d+)\.(\d+)(?:\.(\d+))?/i);
  if (!match) {
    return null;
  }
  return {
    command,
    prefix,
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3] || 0),
    label: match[0],
  };
}

function findPython() {
  const configured = process.env.PYTHON;
  const candidates = configured
    ? [{ command: configured, prefix: [] }]
    : isWindows
      ? [
          { command: "py", prefix: ["-3.12"] },
          { command: "python", prefix: [] },
          { command: "python3", prefix: [] },
        ]
      : [
          { command: "python3.12", prefix: [] },
          { command: "python3", prefix: [] },
          { command: "python", prefix: [] },
        ];

  for (const candidate of candidates) {
    const detected = versionOf(candidate.command, candidate.prefix);
    if (!detected) {
      continue;
    }
    if (detected.major < 3 || (detected.major === 3 && detected.minor < 12)) {
      throw new Error(
        `${detected.label} is too old. Python 3.12+ is required; set PYTHON to a 3.12 executable.`,
      );
    }
    return detected;
  }

  throw new Error(
    'Python 3.12+ was not found. Install it or set PYTHON to the executable path.',
  );
}

function envValue(text, key) {
  const match = text.match(new RegExp(`^${key}=(.*)$`, "m"));
  if (!match) {
    return null;
  }
  return match[1].trim().replace(/^(['"])(.*)\1$/, "$2");
}

function main() {
  const nodeMajor = Number(process.versions.node.split(".")[0]);
  if (nodeMajor < 22) {
    throw new Error(`Node.js 22+ is required; current version is ${process.versions.node}.`);
  }

  const envExample = path.join(root, ".env.example");
  const envFile = path.join(root, ".env");
  if (!existsSync(envFile) && existsSync(envExample)) {
    copyFileSync(envExample, envFile);
    console.log("Created .env from .env.example");
  }

  if (!existsSync(venvPython)) {
    const python = findPython();
    console.log(`Creating .venv with ${python.label}`);
    run(python.command, [...python.prefix, "-m", "venv", ".venv"]);
  } else {
    const existing = versionOf(venvPython);
    if (!existing) {
      throw new Error(`Could not run ${venvPython}. Remove .venv and retry the bootstrap.`);
    }
    if (existing.major < 3 || (existing.major === 3 && existing.minor < 12)) {
      throw new Error(
        `.venv uses ${existing.label}. Remove .venv or create it with Python 3.12+.`,
      );
    }
  }

  console.log("Installing Python dependencies");
  runPython(["-m", "pip", "install", "--upgrade", "pip"]);
  runPython(["-m", "pip", "install", "-e", "apps/api[dev]"]);

  console.log("Installing JavaScript dependencies");
  run(pnpm, ["install", "--frozen-lockfile"], {}, { shell: isWindows });

  for (const directory of ["artifacts", "backups", "logs", "staging"]) {
    mkdirSync(path.join(root, "storage", directory), { recursive: true });
  }

  console.log("Applying database migrations");
  runPython([
    "-m",
    "alembic",
    "-c",
    "apps/api/alembic.ini",
    "upgrade",
    "head",
  ]);

  const envText = existsSync(envFile) ? readFileSync(envFile, "utf8") : "";
  const configuredDataDir = envValue(envText, "LEGACY_DATA_DIR") || "../data";
  const dataDir = path.isAbsolute(configuredDataDir)
    ? configuredDataDir
    : path.resolve(root, configuredDataDir);
  if (existsSync(dataDir)) {
    console.log(`Importing legacy cards from ${dataDir}`);
    runPython([
      "-m",
      "app.cli",
      "import-legacy",
      "--data-dir",
      dataDir,
    ]);
  } else {
    console.log(`Skipping legacy import: ${dataDir} does not exist`);
  }

  console.log("\nBootstrap complete. Start the development services with:");
  console.log("  pnpm dev");
}

try {
  main();
} catch (error) {
  console.error(`\nBootstrap failed: ${error.message}`);
  process.exit(1);
}

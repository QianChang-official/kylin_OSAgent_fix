#!/usr/bin/env node
import { lstat, realpath } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";

const ALLOWED_ENVIRONMENT = new Set([
  "PATH",
  "HOME",
  "USERPROFILE",
  "USER",
  "USERNAME",
  "APPDATA",
  "LOCALAPPDATA",
  "TEMP",
  "TMP",
  "TMPDIR",
  "SYSTEMROOT",
  "WINDIR",
  "COMSPEC",
  "PATHEXT",
  "LANG",
  "LC_ALL",
  "TERM",
  "HTTP_PROXY",
  "HTTPS_PROXY",
  "NO_PROXY",
  "http_proxy",
  "https_proxy",
  "no_proxy",
  "SSL_CERT_FILE",
  "SSL_CERT_DIR",
  "OPENAI_API_KEY",
  "CODEX_API_KEY",
  "CODEX_HOME",
  "CODEX_SECURITY_STATE_DIR",
]);

function usage() {
  return [
    "Usage:",
    "  npm run scan -- --repository <path> --output-dir <path> [options]",
    "",
    "Options:",
    "  --dry-run                    Validate inputs without starting a scan",
    "  --mode standard|deep          Scan mode (default: standard)",
    "  --auth auto|api-key|chatgpt   Credential source (default: auto)",
    "  --max-cost <usd>              Optional estimated cost limit",
    "  --knowledge-base <path>       Approved context file/directory; repeatable",
  ].join("\n");
}

function parseArguments(argv) {
  const parsed = {
    repository: "",
    outputDir: "",
    dryRun: false,
    mode: "standard",
    auth: "auto",
    knowledgeBasePaths: [],
    maxCostUsd: undefined,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--dry-run") {
      parsed.dryRun = true;
      continue;
    }
    if (argument === "--help" || argument === "-h") {
      process.stdout.write(`${usage()}\n`);
      process.exit(0);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`Missing value for ${argument}`);
    }
    index += 1;
    if (argument === "--repository") parsed.repository = value;
    else if (argument === "--output-dir") parsed.outputDir = value;
    else if (argument === "--mode") parsed.mode = value;
    else if (argument === "--auth") parsed.auth = value;
    else if (argument === "--knowledge-base") parsed.knowledgeBasePaths.push(value);
    else if (argument === "--max-cost") parsed.maxCostUsd = Number(value);
    else throw new Error(`Unknown argument: ${argument}`);
  }
  if (!parsed.repository || !parsed.outputDir) {
    throw new Error("--repository and --output-dir are required");
  }
  if (!["standard", "deep"].includes(parsed.mode)) {
    throw new Error("--mode must be standard or deep");
  }
  if (!["auto", "api-key", "chatgpt"].includes(parsed.auth)) {
    throw new Error("--auth must be auto, api-key, or chatgpt");
  }
  if (
    parsed.maxCostUsd !== undefined &&
    (!Number.isFinite(parsed.maxCostUsd) || parsed.maxCostUsd <= 0 || parsed.maxCostUsd > 1000)
  ) {
    throw new Error("--max-cost must be between 0 and 1000 USD");
  }
  return parsed;
}

async function checkedDirectory(path, label) {
  const absolute = resolve(path);
  const metadata = await lstat(absolute);
  if (!metadata.isDirectory() || metadata.isSymbolicLink()) {
    throw new Error(`${label} must be a non-symlink directory`);
  }
  return realpath(absolute);
}

async function checkedKnowledgePath(path) {
  const absolute = resolve(path);
  const metadata = await lstat(absolute);
  if (metadata.isSymbolicLink() || (!metadata.isDirectory() && !metadata.isFile())) {
    throw new Error("Knowledge-base paths must be regular files or directories, not links");
  }
  return realpath(absolute);
}

async function checkedOutputPath(path, repository) {
  const absolute = resolve(path);
  const parent = await checkedDirectory(dirname(absolute), "Output parent");
  const output = resolve(parent, absolute.slice(dirname(absolute).length + 1));
  if (isContained(repository, output)) {
    throw new Error("Output directory must be outside the scanned repository");
  }
  try {
    const metadata = await lstat(output);
    if (metadata.isSymbolicLink() || !metadata.isDirectory()) {
      throw new Error("Existing output path must be a non-symlink directory");
    }
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
  return output;
}

function isContained(root, candidate) {
  const child = relative(root, candidate);
  return child === "" || (child !== ".." && !child.startsWith(`..${sep}`) && !isAbsolute(child));
}

function sanitizeEnvironment() {
  for (const key of Object.keys(process.env)) {
    if (!ALLOWED_ENVIRONMENT.has(key)) delete process.env[key];
  }
  process.env.CODEX_SECURITY_NO_UPDATE_NOTICE = "1";
}

function publicPreflight(plan) {
  return {
    kind: "preflight",
    repository: plan.repository,
    target: plan.target?.kind,
    mode: plan.mode,
    outputDir: plan.outputDir,
    auth: plan.auth,
  };
}

function publicResult(result) {
  return {
    kind: "completed_scan",
    scanDir: result.scanDir,
    reportPath: result.reportPath,
    manifestPath: result.manifestPath,
    findingsPath: result.findingsPath,
    coveragePath: result.coveragePath,
    sarifPath: result.sarifPath,
    pluginVersion: result.pluginVersion,
    coverage: result.coverage?.completeness ?? "unknown",
    findingCount: Array.isArray(result.findings?.findings) ? result.findings.findings.length : 0,
    estimatedCostUsd: result.cost?.estimatedUsd ?? null,
  };
}

async function main() {
  const args = parseArguments(process.argv.slice(2));
  const repository = await checkedDirectory(args.repository, "Repository");
  const outputDir = await checkedOutputPath(args.outputDir, repository);
  const knowledgeBasePaths = [];
  for (const path of args.knowledgeBasePaths) {
    knowledgeBasePaths.push(await checkedKnowledgePath(path));
  }
  sanitizeEnvironment();
  const { CodexSecurity } = await import("@openai/codex-security");
  const security = new CodexSecurity();
  const options = {
    outputDir,
    mode: args.mode,
    auth: args.auth,
    knowledgeBasePaths,
    ...(args.maxCostUsd === undefined ? {} : { maxCostUsd: args.maxCostUsd }),
  };
  try {
    const result = args.dryRun
      ? publicPreflight(await security.preflight(repository, options))
      : publicResult(await security.run(repository, options));
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } finally {
    await security.close();
  }
}

main().catch((error) => {
  process.stderr.write(`codex-security runner: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});

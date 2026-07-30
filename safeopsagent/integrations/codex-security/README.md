# Codex Security scan runner

This optional runner keeps `@openai/codex-security` outside the SafeOpsAgent
production backend. It is intended for a supported x64/arm64 CI worker or
isolated scan host, not the Kylin LoongArch64 runtime.

Prerequisites:

- Node.js 22.13 or later and Python 3.10 or later.
- Codex Security access for the selected credential. An API key or ChatGPT
  login alone does not grant that access.
- Authorization to assess the repository.

Install the exact dependency graph without running package lifecycle scripts:

```bash
npm ci --ignore-scripts
```

Run local-only preflight validation first:

```bash
npm run scan -- \
  --repository /path/to/safeopsagent \
  --output-dir /private/path/outside/repository/scan-20260730 \
  --dry-run
```

Run a report-only scan with an explicit cost estimate limit:

```bash
npm run scan -- \
  --repository /path/to/safeopsagent \
  --output-dir /private/path/outside/repository/scan-20260730 \
  --auth api-key \
  --max-cost 5 \
  --knowledge-base /path/to/safeopsagent/docs/security-design.md
```

The runner removes unrelated environment variables before starting the SDK,
rejects linked repository/context paths, and requires output outside the
repository. Scan reports can contain source excerpts and vulnerability
details; keep the result directory private. SafeOpsAgent imports only sealed,
hash-verified summaries and never executes remediation from a report.

Official documentation:

- <https://developers.openai.com/codex/security/cli>
- <https://developers.openai.com/codex/security/sdk>

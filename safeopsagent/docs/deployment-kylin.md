# 银河麒麟 / Linux 部署说明

本文档说明 SafeOpsAgent v1.3.0 在银河麒麟 V11、Linux、WSL 或类似环境中的最小部署方式。默认部署仅启动 FastAPI 后端及其同源 Vue 控制台 `/console/`；Streamlit 是可选备用前端，不是 Kylin 默认运行入口。

## 1. 环境要求

推荐：

- Python 3.10+，建议 Python 3.11。
- 可访问本机 `127.0.0.1`。
- Linux/Kylin 常用运维命令：`ss`、`lsof`、`netstat`、`ps`、`df`、`free`、`systemctl`、`journalctl`。

命令缺失不会导致后端崩溃，但相关工具会返回环境能力受限。完整演示建议在银河麒麟、Linux 或 WSL 中完成。

## 2. 解压交付包

```bash
mkdir safeops-review
tar -xzf safeopsagent-<tag-commit-short-hash>-final-delivery.tar.gz -C safeops-review
cd safeops-review/safeopsagent
```

交付包内顶层目录为 `safeopsagent/`，不包含 `.git`、虚拟环境、`node_modules`、运行时数据库或真实 API Key。

## 3. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

安装 Kylin 默认后端依赖：

```bash
python -m pip install -r backend/requirements-kylin.txt
```

该依赖集合用于 FastAPI 后端、同源 Vue 控制台和核心安全链路，不包含 Streamlit、MCP SDK、本地大模型或 openGauss。

如需运行自动化测试，再额外安装：

```bash
python -m pip install -r backend/requirements-dev.txt
```

如开发环境确需 Streamlit 备用前端，可人工安装完整 `backend/requirements.txt`；LoongArch64 默认部署不执行此步骤。

## 4. 配置运行模式

### 离线安全模式

```bash
export MODEL_PROVIDER=offline_safe
export PYTHONPATH="$(pwd)"
```

离线安全模式不依赖外网、API Key、本地大模型或 openGauss，仍然走完整安全链路。

### DeepSeek 模型服务模式

真实 API Key 只通过当前 shell 环境变量注入，不写入 `.env`、文档、截图或提交包。

```bash
export MODEL_PROVIDER=deepseek
export MODEL_API_BASE=https://api.deepseek.com
export MODEL_API_KEY=<your-api-key>
export MODEL_NAME=deepseek-chat
export PYTHONPATH="$(pwd)"
```

Qwen / Kimi 可使用：

```bash
export MODEL_PROVIDER=qwen
export MODEL_API_KEY=<your-api-key>
export MODEL_NAME=<configured-model-name>
```

或：

```bash
export MODEL_PROVIDER=kimi
export MODEL_API_KEY=<your-api-key>
export MODEL_NAME=<configured-model-name>
```

兼容变量：

- `MODEL_*` 新变量优先。
- `DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`、`MOONSHOT_API_KEY` 可作为厂商 Key。
- `LLM_*` 旧变量仍兼容。

配置不完整或请求异常时会安全降级为 `offline_safe`。

## 5. 启动后端和 Vue 控制台

```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

访问：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/console/
```

Vue 控制台由 FastAPI 同源托管，运行时不需要 Node、Streamlit 或 pyarrow。已验证路径：

```text
/console/
/console/diagnosis
/console/security
/console/tools
/console/audit
```

如 `8000` 被占用，可更换端口。例如官方复验中最新实例使用 `18080`。

## 6. 运行兼容性检查

后端启动后执行：

```bash
python scripts/compatibility_check.py --table
```

说明：

- 脚本不会启动或停止系统服务。
- 脚本不会执行危险命令。
- 脚本只追加一条标记为 `compatibility_check` 的最小审计记录。
- HTTP 检查使用短 timeout。
- 如果后端未启动，HTTP 项会显示 skip，而不是全部判为 fail。

## 7. 离线 smoke 测试

终端 1：

```bash
bash scripts/offline-start-backend.sh
```

终端 2：

```bash
bash scripts/offline-smoke-test.sh
```

覆盖项：

- `/health`
- `/tools/list`
- `/tools/call get_memory_status`
- `/chat` 正常只读请求
- `/chat` 高危请求拒绝
- `/audit/logs`
- `/audit/trace/{request_id}`

该路径不依赖外网、API Key、DeepSeek、本地模型、openGauss 或 MCP SDK。

## 8. systemd 可选部署

`deploy/install.sh` 会：

- 使用脚本自身路径定位项目根目录。
- 创建 `/opt/safeopsagent/data`。
- 创建 `/etc/safeops-agent/env.conf`，如果已存在则不覆盖。
- 安装 systemd service 文件。
- 默认只启用并启动 `safeops-agent.service`；Vue 控制台由该 FastAPI 服务同源托管。
- 保留 `safeops-web.service`，但不默认启用 Streamlit。

建议 `/etc/safeops-agent/env.conf` 使用：

```text
MODEL_PROVIDER=offline_safe
MODEL_API_BASE=
MODEL_API_KEY=
MODEL_NAME=
BACKEND_URL=http://127.0.0.1:8000
```

如需模型服务模式，在该文件中填入 `MODEL_*` 环境变量。API Key 只能放在部署环境中，不写入代码仓库。

如开发环境确实需要 Streamlit，并已安装完整依赖，可由管理员手动启用：

```bash
/opt/safeopsagent/venv/bin/pip install -r /opt/safeopsagent/backend/requirements.txt
systemctl enable --now safeops-web
```

LoongArch64 最小部署不需要 Node、Streamlit 或 pyarrow。

## 9. 官方 Kylin V11 LoongArch64 v1.2 RC 复验

v1.2 RC 复验环境：

```text
OS: Kylin Linux Advanced Server V11 (Swan25)
Arch: loongarch64
Kernel: 6.6.0-32.7.v2505.ky11.loongarch64
Python: 3.11.6
User: vmuser
Code/package baseline: 57d90f8
Package: safeopsagent-57d90f8-v1.2-rc-kylin-retest.tar.gz
```

通过项：

```text
pytest: 232 passed, 6 skipped
backend import: import-ok
/health: pass
/agent/status: pass
/system/probe: pass
/tools/list: 16 tools
/chat combined diagnosis: memory + CPU + disk
/chat check CPU status: get_cpu_status executed=true
/chat rm -rf /: risk_score=100, reject, executed=false
/chat Prompt Injection: risk_score=100, reject, executed=false
/chat /etc/shadow: risk_score=100, reject, executed=false
/tools/call cleanup scan/plan: pass
/tools/confirm quarantine/restore: pass
confirmation replay/expiry/TOCTOU: pass
/audit/logs: pass
/audit/trace/{request_id}: pass
shell=True: no result
subprocess.run: only SafeExecutor
```

Vue 控制台：

```text
/console/: 200
/console/diagnosis: 200
/console/security: 200
/console/tools: 200
/console/audit: 200
Kylin 龙芯浏览器 headless screenshots: pass
```

DeepSeek 真实 Key 受控联调：

```text
agent_mode: model_api
model_provider: deepseek
model_vendor: DeepSeek
model_name: deepseek-chat
planner_source: domestic_model
check memory status -> get_memory_status, executed=true
rm -rf / -> risk_score=100, reject, executed=false
Prompt Injection -> risk_score=100, reject, executed=false
/etc/shadow -> risk_score=100, reject, executed=false
API / Audit Trace / Uvicorn log: no API Key leak
```

边界：

- 官方 v1.2 RC 复验包不包含 `.git`，版本通过包名、SHA256 和独立复验目录确认。
- 麒麟真机复验基线为 `57d90f8`，验证了核心安全闭环、多工具联合诊断、可恢复清理、危险拒绝、审计与 Vue 控制台。
- v1.3.0 新增根因分析引擎、配置漂移/僵尸进程/磁盘 I/O 三个场景工具与 MCP SSE 传输，已在本地完成 52 项自动化测试验证；建议在麒麟目标机重跑 `python -m pytest -q` 与 `python scripts/performance_test.py` 补充真机基线。
- DeepSeek Key 仅用于受控联调，不写入配置文件或提交包。

## 10. 常见问题

### pip 安装慢或无网络

优先使用离线安全模式验证后端核心链路。LoongArch64 低资源环境可先使用 `backend/requirements-kylin.txt`。

### lsof / netstat / systemctl / journalctl 缺失

相关工具会返回环境能力受限。根据目标系统安装对应系统包即可，不代表 SafeOpsAgent 安全链路失败。

### journalctl 权限不足

使用具备日志读取权限的用户运行，或在演示中说明当前环境权限受限。

### 端口被占用

更换 uvicorn 端口，并使用对应地址访问 `/console/` 与 API。

### Windows 与 Kylin 差异

Windows 可用于接口和前端演示，但缺少部分 Linux 运维命令。完整 OS 能力验证建议在银河麒麟、Linux 或 WSL 中完成。

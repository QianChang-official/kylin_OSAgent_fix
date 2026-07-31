# Changelog

本文件记录对外可见的变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

版本号的唯一来源是 `safeopsagent/backend/__init__.py` 的 `__version__`；
打包元数据与运行时 `/health` 自述版本都由它派生，不会各说各话。

## [未发布]

### 新增

- **审计哈希链**。每条审计记录提交自身列的 SHA-256 摘要并链接前一条。改写、
  删除、重排以及整张日表丢失都能在重算时暴露，并定位到具体行与 `request_id`。
- **审计签名**。配置 `AUDIT_HMAC_KEY` 后，每个链接附 HMAC-SHA256 签名。完整性
  与真实性在验证报告中分开陈述：未配置密钥时，有数据库写权限者可整体重建一条
  自洽的链，此边界由 `test_the_same_forgery_is_invisible_without_a_key` 固定。
- **离线审计验证器** `scripts/verify_audit_chain.py`。仅凭数据库文件核对，不需要
  后端在跑，破损时非零退出并给出首个断点。
- **INV-R8** 加入安全不变式门禁：改写与删除两种攻击各跑一次真实检测。
- CI 新增 `Audit chain is tamper-evident` 步骤：篡改后若仍验证通过则构建失败。
- `pyproject.toml`：标准构建元数据、`ruff` 与 `pytest` 配置集中于此。运行时依赖
  不在此重复声明，而是动态读取 `backend/requirements.txt`，避免两处漂移。
- `LICENSE` (Apache-2.0) 与 `NOTICE`。此前仓库无授权文件，法律上默认保留全部
  权利，他人不可使用。
- `SECURITY.md`：信任边界、审计可信度的能与不能、已知限制、漏洞报告流程。
- `CONTRIBUTING.md`。
- `backend/tests/test_packaging_metadata.py`：让版本号与依赖的"单一来源"成为被
  测试保护的性质，而不是靠人记得同步。

### 变更

- **审计写入改为 fail-closed**。`AuditLogger.log()` 失败时抛 `AuditWriteError`
  而非打印警告并返回 `False`。`/chat`、`/tools/call`、`/tools/confirm` 及经
  `mcp_adapter` 委派的两种 MCP 传输，在工具执行**前**调用 `preflight()`，审计
  不可写时拒绝执行并返回 503。
- 版本号来源从 `backend/app.py` 的字面量收敛到 `backend/__init__.py` 的
  `__version__`；`backend.app.APP_VERSION` 与 `scripts/package-final.py` 均改为
  引用它。
- 可直接运行 `pytest`，不再需要手动导出 `PYTHONPATH`。

### 修复

- `AuditLogger._audit_tables()` 排除 `audit_chain_head`。该表匹配 `audit_%`
  模式，否则 `trace()` 会扫到链头表并因缺列报错。
- 本次触及的 SQLite 连接改用 `contextlib.closing`。未关闭的连接在 Windows 上会
  占住文件句柄，导致后续文件操作失败。

### 修正的既有矛盾

- INV-R2 要求每次请求都产生可回放的审计记录，但 `log()` 此前静默失败且请求照常
  成功。不变式在测试环境成立、在磁盘满或权限错时不成立。现已一致。
- 文档中 11 处以"append-only 不可清除"作为审计不可否认性的依据，而实现只是应用层
  不提供删除接口。现已补上真正的防篡改机制，并在 `SECURITY.md` 中写明其边界。

## [1.3.0]

银河麒麟 V11 LoongArch64 真机复验版本。17 个受控运维工具、跨工具根因分析、
变更—故障因果关联、操作影响面预测、自学习基线监控、五层安全护栏、MCP stdio 与
SSE 双传输、Vue 控制台、全链路审计追踪、前门欺骗与被动溯源取证。

> 1.3.0 及更早版本的详细变更未按本格式记录，可参阅 `docs/` 下的设计与测试文档
> 及提交历史。本文件自本次起维护。

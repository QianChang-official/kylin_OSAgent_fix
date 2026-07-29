# kylin_OSAgent_fix

面向银河麒麟操作系统的安全智能运维 Agent —— 第十五届中国软件杯 A 组赛题作品仓库。

出题企业：麒麟软件有限公司
目标环境：银河麒麟高级服务器版 V11 (Swan25) / LoongArch64

## 仓库结构

```
safeopsagent/          项目主体（后端、前端、脚本、交付文档）
```

项目说明、部署方式与全部交付文档见 [`safeopsagent/README.md`](safeopsagent/README.md)。

## 快速开始

```bash
cd safeopsagent
python3 -m pip install -r backend/requirements-kylin.txt
export MODEL_PROVIDER=offline_safe
export PYTHONPATH="$(pwd)"
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000/console/`。

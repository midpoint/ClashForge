# ClashForge 开发说明

## 环境与测试
- 本地虚拟环境：`.venv/`（uv 创建，已 gitignore），运行脚本优先用 `.venv/bin/python`。
- 单元测试：`.venv/bin/python -m pytest tests/ -q`（纯离线，不联网）。
- 测试依赖：`uv pip install --python .venv/bin/python -r requirements-dev.txt`。

## 常用命令
- 完整抓取 + 测速 + 生成：`python3 ClashForge.py`
- 仅用本机网络复测现有 `clash_config.yaml`：`python3 ClashForge.py --check-only`
  - 只输出 `clash_config_featured_cn.yaml`（境内延迟最低的前 100 个节点）
  - 不覆盖 `clash_config.yaml` / `clash_config_featured.yaml`
- 定时复测：`check.sh`（crontab `23 */6 * * *`）。它在临时 worktree 中基于 `origin/main` 运行，只把 `clash_config_featured_cn.yaml` 提交并推送；日志写入 `check.log`。

## 订阅来源约定
- 公开订阅：`input/subscriptions.txt`（或 `input/*.txt`），一行一个链接，`#` 开头为注释。
- 付费/私密订阅：只放环境变量 `CLASHFORGE_PRIVATE_SUBSCRIPTIONS`、`CLASHFORGE_PRIVATE_SUBSCRIPTIONS_FILE` 或 `input/*_private.txt`（已 gitignore）。
- **不要把带 token/密钥的订阅链接写入仓库、提交信息或日志**。日志中的链接默认脱敏（`CLASHFORGE_LOG_URLS=1` 可关闭，仅限本地调试）。

## CI 与境内使用
- `.github/workflows/main.yml`：GitHub 托管 runner 在境外，每 5 小时抓取、测速并提交 `clash_config.yaml` + `clash_config_featured.yaml`。
- 境外测通的节点在境内可能大量超时，境内可用性以 `--check-only` / `check.sh` 生成的 CN 精选为准。

## 提交与推送
- 提交信息用中文，结尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 推送：`GIT_TERMINAL_PROMPT=0 git push origin main`。origin 是镜像地址，凭据由 credential store 管理，不要打印或回显凭据。
- 提交前先跑 `pytest tests/ -q`。

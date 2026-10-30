#!/usr/bin/env bash
# ClashForge 境内复测脚本，由 cron 每 6 小时调用。
# 在临时 worktree 中取远端最新代码和配置，用本机网络（中国境内）复测，
# 生成 clash_config_featured_cn.yaml 并推送到远端 main。
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"

export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export GIT_TERMINAL_PROMPT=0

LOG="$ROOT/check.log"
exec >>"$LOG" 2>&1
echo "===== $(date '+%F %T') check.sh 开始 ====="

# 防止上一次还没跑完又启动
exec 9>/tmp/clashforge-check.lock
if ! flock -n 9; then
  echo "已有 check.sh 在运行，本次跳过"
  exit 0
fi

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

TMP_DIR="$(mktemp -d)"
WORKTREE="$TMP_DIR/repo"

cleanup() {
  cd "$ROOT" 2>/dev/null || true
  git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# 基于远端最新代码/配置运行，不受本地未提交改动影响
git fetch origin main
git worktree add --detach "$WORKTREE" origin/main >/dev/null

# 复用已经下载好的 mihomo 内核，避免每次重新下载
if [ -f "$ROOT/clash-linux" ]; then
  cp -f "$ROOT/clash-linux" "$WORKTREE/clash-linux"
fi

cd "$WORKTREE"
"$PY" ClashForge.py --check-only

if [ ! -s clash_config_featured_cn.yaml ]; then
  echo "错误：未生成 clash_config_featured_cn.yaml"
  exit 1
fi

git add clash_config_featured_cn.yaml
if git diff --cached --quiet; then
  echo "CN 精选订阅没有变化，无需推送"
  exit 0
fi

git commit -m "本地复测更新 CN 精选订阅 $(date -u '+%Y-%m-%dT%H:%MZ')"

ok=0
for attempt in 1 2 3; do
  if git push origin HEAD:main; then
    ok=1
    break
  fi
  echo "推送失败（第 $attempt 次），尝试同步远端..."
  git fetch origin main
  git rebase origin/main
  sleep $((attempt * 5))
done
if [ "$ok" != 1 ]; then
  echo "错误：推送 CN 精选订阅失败"
  exit 1
fi
echo "已推送 clash_config_featured_cn.yaml"

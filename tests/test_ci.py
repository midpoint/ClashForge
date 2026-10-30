from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "main.yml"


def test_workflow_does_not_depend_on_manual_pat():
    # 2026-02-19 起所有运行都卡在 checkout：secrets.BOT 过期后 git 回退到交互式
    # 凭据输入（terminal prompts disabled），改用仓库内置 GITHUB_TOKEN
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "${{ secrets.BOT }}" not in text

    doc = yaml.safe_load(text)
    assert doc["permissions"]["contents"] == "write"

    job = next(iter(doc["jobs"].values()))
    checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout"))
    assert "token" not in checkout.get("with", {})


def test_workflow_gives_script_api_token():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in text


def test_github_api_headers(cf, monkeypatch):
    monkeypatch.setattr(cf, "GITHUB_TOKEN", "tkn")
    assert cf.github_api_headers()["Authorization"] == "Bearer tkn"

    monkeypatch.setattr(cf, "GITHUB_TOKEN", None)
    assert "Authorization" not in cf.github_api_headers()

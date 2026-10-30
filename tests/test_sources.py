from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_links_moved_out_of_main():
    src = (ROOT / "ClashForge.py").read_text(encoding="utf-8")
    main_block = src[src.index("if __name__ == '__main__':"):]
    assert "https://" not in main_block, "订阅链接不应再硬编码在 __main__ 里"

    lines = [line.strip() for line in
             (ROOT / "input" / "subscriptions.txt").read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    assert len(lines) >= 50
    assert all(line.startswith(("http://", "https://")) for line in lines)


def test_split_private_links(cf):
    value = ("https://a.example/sub?token=1\n\n# 注释\n"
             "https://b.example/sub,https://c.example/sub;https://d.example/sub")
    assert cf.split_private_links(value) == [
        "https://a.example/sub?token=1",
        "https://b.example/sub",
        "https://c.example/sub",
        "https://d.example/sub",
    ]


def test_read_private_links_from_env(cf, tmp_path, monkeypatch):
    monkeypatch.setenv(cf.PRIVATE_LINKS_ENV, "https://paid.example/sub?token=secret")
    monkeypatch.delenv(cf.PRIVATE_LINKS_FILE_ENV, raising=False)

    assert cf.read_private_links(str(tmp_path)) == ["https://paid.example/sub?token=secret"]


def test_read_private_links_from_file_and_input_dir(cf, tmp_path, monkeypatch):
    monkeypatch.delenv(cf.PRIVATE_LINKS_ENV, raising=False)
    outside = tmp_path / "outside.txt"
    outside.write_text("https://file.example/sub\n", encoding="utf-8")
    monkeypatch.setenv(cf.PRIVATE_LINKS_FILE_ENV, str(outside))
    (tmp_path / "paid_private.txt").write_text("# 注释\nhttps://dir.example/sub\n", encoding="utf-8")

    assert cf.read_private_links(str(tmp_path)) == [
        "https://file.example/sub",
        "https://dir.example/sub",
    ]


def test_read_txt_files_excludes_private_files(cf, tmp_path):
    (tmp_path / "public.txt").write_text("# 注释\nhttps://public.example/sub\n", encoding="utf-8")
    (tmp_path / "paid_private.txt").write_text("https://paid.example/sub\n", encoding="utf-8")

    assert cf.read_txt_files(str(tmp_path)) == ["https://public.example/sub"]


def test_mask_url_hides_credentials(cf, monkeypatch):
    monkeypatch.setattr(cf, "LOG_MASK_URLS", True)
    masked = cf.mask_url("https://sub.example.com/api/v1/sub?token=SECRET")
    assert masked == "https://sub.example.com/…"
    assert "SECRET" not in masked
    assert cf.mask_url("http://1.2.3.4:8080/sub?token=x") == "http://1.2.3.4:8080/…"

    monkeypatch.setattr(cf, "LOG_MASK_URLS", False)
    assert "SECRET" in cf.log_url("https://sub.example.com/api/v1/sub?token=SECRET")


def test_mask_error_strips_url_from_exception_text(cf, monkeypatch):
    monkeypatch.setattr(cf, "LOG_MASK_URLS", True)
    error = Exception("Max retries exceeded with url: /api/v1/sub?token=SECRET (Caused by NewConnectionError)")

    text = cf.mask_error(error, "https://sub.example.com/api/v1/sub?token=SECRET")

    assert "SECRET" not in text
    assert "<masked>" in text

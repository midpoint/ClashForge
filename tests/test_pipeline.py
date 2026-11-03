import asyncio
import json
import os
import threading
import time

import yaml


def _yaml_sub(server, name):
    return yaml.dump({"proxies": [{
        "name": name, "server": server, "port": 443,
        "type": "ss", "cipher": "aes-256-gcm", "password": "p",
    }]})


def test_generate_fetches_sources_concurrently(cf, tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "CONFIG_FILE", str(tmp_path / "clash_config.yaml"))
    barrier = threading.Barrier(5, timeout=5)

    def fake_fetch(url):
        barrier.wait()  # 串行抓取凑不齐 5 个线程，会抛 BrokenBarrierError
        return _yaml_sub(url, url.rsplit("/", 2)[-2])

    monkeypatch.setattr(cf, "_fetch_url_content", fake_fetch)
    links = [f"https://s{i}.example/sub" for i in range(5)]

    cf.generate_clash_config(links, [])

    config = yaml.safe_load((tmp_path / "clash_config.yaml").read_text(encoding="utf-8"))
    assert len(config["proxies"]) == 5


def test_generate_js_renders_pages_when_needed(cf, tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "CONFIG_FILE", str(tmp_path / "clash_config.yaml"))
    monkeypatch.setattr(cf, "_fetch_url_content", lambda url: "<html>need js</html>")
    monkeypatch.setattr(cf, "js_render", lambda url, timeout=None: yaml.dump({
        "external-controller": "127.0.0.1:9090",
        "proxies": [{"name": "js-node", "server": "9.9.9.9", "port": 443,
                     "type": "ss", "cipher": "aes-256-gcm", "password": "p"}],
    }))

    cf.generate_clash_config(["https://js.example/sub"], [])

    config = yaml.safe_load((tmp_path / "clash_config.yaml").read_text(encoding="utf-8"))
    assert [p["name"] for p in config["proxies"]] == ["js-node"]


def test_generate_skips_fetch_when_budget_exhausted(cf, tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "CONFIG_FILE", str(tmp_path / "clash_config.yaml"))
    monkeypatch.setattr(cf, "FETCH_BUDGET", 0)

    def must_not_fetch(url):
        raise AssertionError("预算为 0 时不应发起抓取")

    monkeypatch.setattr(cf, "_fetch_url_content", must_not_fetch)

    cf.generate_clash_config(["https://a.example/sub"], [])

    assert not (tmp_path / "clash_config.yaml").exists()


def test_generate_caps_js_render_calls(cf, tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "CONFIG_FILE", str(tmp_path / "clash_config.yaml"))
    monkeypatch.setattr(cf, "MAX_JS_RENDERS", 1)
    monkeypatch.setattr(cf, "_fetch_url_content", lambda url: "<html>need js</html>")
    calls = []

    def fake_render(url, timeout=None):
        calls.append(url)
        return _yaml_sub(url, f"n{len(calls)}")

    monkeypatch.setattr(cf, "js_render", fake_render)

    cf.generate_clash_config(["https://a.example/sub", "https://b.example/sub"], [])

    assert len(calls) == 1


def test_parse_url_content_extracts_plain_link_list(cf):
    content = "# comment\nss://YWVzLTI1Ni1nY206cHc=@1.2.3.4:8388#plain\n\n"

    nodes, isyaml, needs_render = cf._parse_url_content(content)

    assert needs_render is False
    assert isyaml is False
    assert [n["name"] for n in nodes] == ["plain"]


def test_parse_url_content_only_renders_html(cf):
    _, _, needs_render = cf._parse_url_content("just plain text, nothing here")
    assert needs_render is False

    _, _, needs_render = cf._parse_url_content("<!DOCTYPE html><html><script>x</script></html>")
    assert needs_render is True


def test_md_link_extracts_inline_proxy_links(cf, monkeypatch):
    content = "# list\nss://YWVzLTI1Ni1nY206cHc=@1.2.3.4:8388#mdnode\n"
    monkeypatch.setattr(cf, "_fetch_url_content", lambda url: content)

    _url, nodes, _needs_render, _elapsed = cf._handle_link_job("https://x.example/README.md")

    assert [n["name"] for n in nodes] == ["mdnode"]


def _write_config_file(tmp_path, names):
    path = tmp_path / "clash_config.yaml"
    path.write_text(yaml.dump({
        "proxies": [{"name": n, "server": "1.1.1.1", "port": i + 1, "type": "ss",
                     "cipher": "aes-256-gcm", "password": "p"}
                    for i, n in enumerate(names)],
        "proxy-groups": [
            {"name": "节点选择", "type": "select",
             "proxies": ["自动选择", "故障转移", "DIRECT", "手动选择"]},
            {"name": "自动选择", "type": "url-test", "proxies": list(names)},
            {"name": "故障转移", "type": "fallback", "proxies": list(names)},
            {"name": "手动选择", "type": "select", "proxies": list(names)},
        ],
        "rules": ["DOMAIN,example.com,DIRECT", "MATCH,节点选择"],
    }, allow_unicode=True), encoding="utf-8")
    return path


def test_generate_featured_keeps_top_n_in_delay_order(cf, tmp_path):
    path = _write_config_file(tmp_path, ["a", "b", "c", "d"])
    config = cf.ClashConfig(str(path))
    out = tmp_path / "clash_config_featured.yaml"

    result = cf.generate_featured_config(config, ["c", "a", "d", "b"], limit=2, output=str(out))

    assert result == str(out)
    featured = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert [p["name"] for p in featured["proxies"]] == ["c", "a"]
    groups = {g["name"]: g["proxies"] for g in featured["proxy-groups"]}
    assert groups["自动选择"] == ["c", "a"]
    assert groups["故障转移"] == ["c", "a"]
    assert groups["手动选择"] == ["c", "a"]
    # 总控组只引用其它组，必须原样保留
    assert groups["节点选择"] == ["自动选择", "故障转移", "DIRECT", "手动选择"]
    assert featured["rules"] == ["DOMAIN,example.com,DIRECT", "MATCH,节点选择"]
    # 不能污染主配置
    assert [p["name"] for p in config.config["proxies"]] == ["a", "b", "c", "d"]


def test_generate_featured_skips_without_valid_nodes(cf, tmp_path):
    path = _write_config_file(tmp_path, ["a"])
    config = cf.ClashConfig(str(path))
    out = tmp_path / "featured.yaml"

    assert cf.generate_featured_config(config, [], output=str(out)) is None
    assert not out.exists()


def test_generate_featured_handles_fewer_nodes_than_limit(cf, tmp_path):
    path = _write_config_file(tmp_path, ["a", "b"])
    config = cf.ClashConfig(str(path))
    out = tmp_path / "featured.yaml"

    cf.generate_featured_config(config, ["b", "a"], limit=100, output=str(out))

    featured = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert [p["name"] for p in featured["proxies"]] == ["b", "a"]


def test_test_group_proxies_stops_at_deadline(cf):
    class SlowAPI:
        async def test_proxy_delay(self, name):
            await asyncio.sleep(0.3)
            return cf.ProxyTestResult(name, 10)

    start = time.monotonic()
    results = asyncio.run(cf.test_group_proxies(SlowAPI(), ["a", "b"], timeout=0.05))

    # 第一条结果返回后才发现超预算，最多多等一个请求；但不会把两个都测完
    assert len(results) <= 1
    assert time.monotonic() - start < 1.5


def test_check_only_cli_flag(cf):
    assert cf.parse_args([]).check_only is False
    assert cf.parse_args(["--check-only"]).check_only is True
    assert cf.parse_args(["-c"]).check_only is True


def test_template_groups_use_configured_test_url(cf):
    urls = {g["url"] for g in cf.clash_config_template["proxy-groups"] if "url" in g}
    # 自动选择/故障转移的健康检查都走同一个轻量测速地址
    assert urls == {cf.TEST_URL}


def test_work_check_only_outputs_cn_featured_only(cf, monkeypatch, tmp_path):
    calls = {}
    sanitized = str(tmp_path / "mihomo.yaml")
    monkeypatch.setattr(cf, "SPEED_TEST_ENABLED", False)
    monkeypatch.setattr(cf, "prepare_mihomo_config", lambda path: sanitized)

    def fake_start_clash(**kwargs):
        calls["start"] = kwargs
        return None

    async def fake_proxy_clean(config_path=None, **kwargs):
        calls["clean"] = {"config_path": config_path, **kwargs}

    monkeypatch.setattr(cf, "start_clash", fake_start_clash)
    monkeypatch.setattr(cf, "switch_proxy", lambda *a, **k: None)
    monkeypatch.setattr(cf, "proxy_clean", fake_proxy_clean)

    cf.work([], check=False, only_check=True)

    # 启动和测试都使用规整后的临时 YAML，不再直接读源配置
    assert calls["start"]["config_path"] == sanitized
    # --check-only 不覆盖源配置，只输出 CN 精选
    assert calls["clean"]["config_path"] == sanitized
    assert calls["clean"]["save_config"] is False
    assert calls["clean"]["featured_output"] == cf.CN_FEATURED_FILE
    assert calls["clean"]["speed_test"] is False
    assert calls["clean"]["speed_output"] == cf.CN_SPEED_FEATURED_FILE


def test_work_speed_test_passes_cn_speed_output(cf, monkeypatch):
    calls = {}

    monkeypatch.setattr(cf, "prepare_mihomo_config", lambda path: "sanitized.yaml")
    monkeypatch.setattr(cf, "start_clash", lambda **kwargs: None)
    monkeypatch.setattr(cf, "switch_proxy", lambda *a, **k: None)

    async def fake_proxy_clean(config_path=None, **kwargs):
        calls["clean"] = kwargs

    monkeypatch.setattr(cf, "proxy_clean", fake_proxy_clean)

    cf.work([], only_check=True, speed_test=True)

    assert calls["clean"]["speed_test"] is True
    assert calls["clean"]["speed_output"] == cf.CN_SPEED_FEATURED_FILE


def test_speed_test_cli_flag(cf):
    assert cf.parse_args([]).speed_test is False
    assert cf.parse_args(["--speed-test"]).speed_test is True
    assert cf.parse_args(["-s"]).speed_test is True


def test_speed_featured_sorts_and_filters(cf, monkeypatch):
    speeds = {"a": 1.5, "b": 0.0, "c": 3.0}
    monkeypatch.setattr(cf, "measure_proxy_speed", lambda name, **kwargs: speeds[name])

    names = cf.test_speed_featured(["a", "b", "c"], proxy_port=7890, duration=1, budget=10)

    assert names == ["c", "a"]


def test_normalize_reality_short_id_forces_yaml_string(cf):
    # mihomo 用 Go YAML：不加引号的 08 会变数字 8，导致奇数长度而解析失败
    dumped = yaml.safe_dump({"short-id": cf.normalize_reality_short_id("08")})
    assert "short-id: '08'" in dumped
    # 奇数长度补零，偶数长度保持不变
    assert cf.normalize_reality_short_id("8") == "08"
    assert cf.normalize_reality_short_id("1234") == "1234"
    assert cf.normalize_reality_short_id(None) is None


def test_prepare_mihomo_config_does_not_touch_source(cf, tmp_path):
    source = tmp_path / "clash_config.yaml"
    source.write_text(yaml.dump({
        "proxies": [{
            "name": "r", "type": "vless", "server": "1.1.1.1", "port": 443,
            "reality-opts": {"public-key": "k", "short-id": "08"},
        }],
        "proxy-groups": [], "rules": ["MATCH,DIRECT"],
    }, allow_unicode=True), encoding="utf-8")
    original = source.read_text(encoding="utf-8")
    assert "short-id: 08" in original

    prepared = cf.prepare_mihomo_config(str(source))
    try:
        text = open(prepared, encoding="utf-8").read()
        assert "short-id: '08'" in text
        assert yaml.safe_load(text)["proxies"][0]["reality-opts"]["short-id"] == "08"
    finally:
        os.unlink(prepared)

    assert source.read_text(encoding="utf-8") == original


def test_handle_clash_error_repairs_yaml_without_stale_json(cf, tmp_path):
    yaml_path = tmp_path / "clash_config.yaml"
    yaml_path.write_text(yaml.dump({
        "proxies": [
            {"name": "a", "type": "ss", "server": "1.1.1.1", "port": 1},
            {"name": "b", "type": "ss", "server": "2.2.2.2", "port": 2},
        ],
        "proxy-groups": [{"name": "g", "type": "select", "proxies": ["a", "b", "DIRECT"]}],
        "rules": ["MATCH,g"],
    }, allow_unicode=True), encoding="utf-8")
    # 残留的 .json 不能劫持 YAML 模式的修复
    json_path = tmp_path / "clash_config.yaml.json"
    json_path.write_text(json.dumps({"proxies": [{"name": "old"}]}), encoding="utf-8")

    assert cf.handle_clash_error(
        "Parse config error: proxy 0: invalid REALITY short ID", str(yaml_path))

    repaired = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert [p["name"] for p in repaired["proxies"]] == ["b"]
    assert repaired["proxy-groups"][0]["proxies"] == ["b", "DIRECT"]
    assert json.loads(json_path.read_text(encoding="utf-8"))["proxies"][0]["name"] == "old"

    # 越界索引不应误删节点
    assert cf.handle_clash_error(
        "Parse config error: proxy 99: invalid REALITY short ID", str(yaml_path)) is False
    assert len(yaml.safe_load(yaml_path.read_text(encoding="utf-8"))["proxies"]) == 1

import base64
import copy
import json

import yaml


def _b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def test_hysteria2_keeps_full_password(cf):
    for scheme in ("hysteria2://", "hy2://"):
        link = f"{scheme}9f3e-uuid-pass@1.2.3.4:443?sni=a.com&insecure=1#N1"
        node = cf.parse_hysteria2_link(link)
        assert node is not None
        assert node["password"] == "9f3e-uuid-pass"
        assert node["auth"] == "9f3e-uuid-pass"
        assert node["server"] == "1.2.3.4"
        assert node["port"] == 443


def test_hysteria2_insecure_maps_to_skip_cert_verify(cf):
    node = cf.parse_hysteria2_link("hysteria2://pw@1.2.3.4:443?insecure=1#n")
    assert node["skip-cert-verify"] is True

    node = cf.parse_hysteria2_link("hysteria2://pw@1.2.3.4:443?insecure=0#n")
    assert node["skip-cert-verify"] is False


def test_ss_sip002_base64_userinfo(cf):
    userinfo = _b64("aes-256-gcm:pw")
    node = cf.parse_ss_link(f"ss://{userinfo}@example.com:8388#node")
    assert node["cipher"] == "aes-256-gcm"
    assert node["password"] == "pw"
    assert node["port"] == 8388
    assert node["name"] == "node"


def test_ss_legacy_whole_base64(cf):
    body = _b64("aes-256-gcm:pw@1.2.3.4:8388")
    node = cf.parse_ss_link(f"ss://{body}#legacy")
    assert node["server"] == "1.2.3.4"
    assert node["port"] == 8388
    assert node["cipher"] == "aes-256-gcm"
    assert node["password"] == "pw"


def test_ss_legacy_base64_with_slash(cf):
    # 标准 base64 里的 '/' 会被 urlsplit 切进 path，解析时必须拼回来
    body = base64.b64encode("aes-256-gcm:ÿÿ@1.2.3.4:8388".encode()).decode().rstrip("=")
    assert "/" in body
    node = cf.parse_ss_link(f"ss://{body}#slash")
    assert node is not None
    assert node["server"] == "1.2.3.4"
    assert node["password"] == "ÿÿ"


def test_ss_plain_userinfo(cf):
    node = cf.parse_ss_link("ss://aes-256-gcm:pw@example.com:8388#plain")
    assert node["cipher"] == "aes-256-gcm"
    assert node["password"] == "pw"


def test_ss_missing_port_returns_none(cf):
    userinfo = _b64("aes-256-gcm:pw")
    assert cf.parse_ss_link(f"ss://{userinfo}@example.com#noport") is None


def test_trojan_without_fragment(cf):
    node = cf.parse_trojan_link("trojan://pw@1.2.3.4:443?sni=a.com")
    assert node is not None
    assert node["password"] == "pw"
    assert node["name"] == "1.2.3.4:443"


def test_vless_without_fragment(cf):
    node = cf.parse_vless_link("vless://uuid-1@1.2.3.4:443?security=tls&type=ws&path=%2Fws&host=a.com")
    assert node is not None
    assert node["uuid"] == "uuid-1"
    assert node["network"] == "ws"
    assert node["ws-opts"]["path"] == "/ws"


def test_vless_reality_opts(cf):
    node = cf.parse_vless_link(
        "vless://uuid-1@1.2.3.4:443?security=reality&sni=a.com&fp=chrome"
        "&pbk=PUBKEY&sid=ab12&flow=xtls-rprx-vision#reality"
    )
    assert node["tls"] is True
    assert node["reality-opts"] == {"public-key": "PUBKEY", "short-id": "ab12"}
    assert node["flow"] == "xtls-rprx-vision"
    assert node["client-fingerprint"] == "chrome"


def test_vmess_roundtrip(cf):
    payload = _b64(json.dumps({
        "v": "2", "ps": "vm", "add": "1.2.3.4", "port": 443,
        "id": "uuid-1", "aid": 0, "net": "ws", "path": "/p", "host": "h"
    }))
    node = cf.parse_vmess_link(f"vmess://{payload}")
    assert node["server"] == "1.2.3.4"
    assert node["uuid"] == "uuid-1"
    assert node["ws-opts"]["path"] == "/p"


def test_deduplicate_keeps_distinct_uuids(cf):
    nodes = [
        {"name": "a", "server": "1.1.1.1", "port": 443, "type": "vless", "uuid": "uuid-1"},
        {"name": "b", "server": "1.1.1.1", "port": 443, "type": "vless", "uuid": "uuid-2"},
    ]
    assert len(cf.deduplicate_proxies(nodes)) == 2


def test_deduplicate_drops_nodes_without_server_or_port(cf):
    nodes = [{"name": "bad", "type": "ss"}, {"name": "ok", "server": "1.1.1.1", "port": 1, "type": "ss"}]
    assert len(cf.deduplicate_proxies(nodes)) == 1


def test_proxy_test_result_dedup_by_name(cf):
    a = cf.ProxyTestResult("node", 10)
    b = cf.ProxyTestResult("node", 20)
    assert len({a, b}) == 1


def test_generate_does_not_pollute_template(cf, tmp_path, monkeypatch):
    template_snapshot = copy.deepcopy(cf.clash_config_template)
    monkeypatch.setattr(cf, "CONFIG_FILE", str(tmp_path / "clash_config.yaml"))

    load_nodes = [{"name": "节点A", "server": "2.2.2.2", "port": 443,
                   "type": "ss", "cipher": "aes-256-gcm", "password": "p"}]
    cf.generate_clash_config([], load_nodes)

    assert cf.clash_config_template == template_snapshot
    # 调用方传入的节点对象不应被就地改名
    assert load_nodes[0]["name"] == "节点A"
    assert (tmp_path / "clash_config.yaml").exists()
    assert (tmp_path / "clash_config.yaml.json").exists()


def test_generate_handles_nodes_without_name(cf, tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "CONFIG_FILE", str(tmp_path / "clash_config.yaml"))
    cf.generate_clash_config([], [{"server": "3.3.3.3", "port": 8443,
                                   "type": "ss", "cipher": "aes-256-gcm", "password": "p"}])

    config = yaml.safe_load((tmp_path / "clash_config.yaml").read_text(encoding="utf-8"))
    assert config["proxies"][0]["name"] == "3.3.3.3:8443"


def test_apply_results_sorts_before_limit(cf, tmp_path):
    nodes = [{"name": n, "server": "1.1.1.1", "port": p, "type": "ss",
              "cipher": "aes-256-gcm", "password": "pw"} for n, p in
             [("slow", 1), ("fast", 2), ("dead", 3)]]
    groups = [("节点选择", ["自动选择"]), ("自动选择", ["slow", "fast", "dead"]),
              ("故障转移", ["slow", "fast", "dead"]), ("手动选择", ["slow", "fast", "dead"])]
    path = tmp_path / "clash_config.yaml"
    path.write_text(yaml.dump({"proxies": nodes, "proxy-groups": [
        {"name": name, "type": "select" if name != "自动选择" else "url-test", "proxies": list(names)}
        for name, names in groups]}), encoding="utf-8")

    config = cf.ClashConfig(str(path))
    results = [cf.ProxyTestResult("slow", 200), cf.ProxyTestResult("fast", 10),
               cf.ProxyTestResult("dead", None)]

    valid = config.apply_results(results, ["自动选择", "故障转移", "手动选择"], limit=1)

    assert valid == ["fast"]  # limit=1 时保留延迟最低的
    assert config.get_group_proxies("自动选择") == ["fast"]
    assert [p["name"] for p in config.config["proxies"]] == ["fast"]


def test_apply_results_keeps_untested_group_members(cf, tmp_path):
    nodes = [{"name": n, "server": "1.1.1.1", "port": p, "type": "ss",
              "cipher": "aes-256-gcm", "password": "pw"} for n, p in
             [("a", 1), ("b", 2), ("custom", 3)]]
    groups = [("自动选择", ["a", "b"]), ("自定义", ["custom", "a"])]
    path = tmp_path / "clash_config.yaml"
    path.write_text(yaml.dump({"proxies": nodes, "proxy-groups": [
        {"name": name, "type": "select", "proxies": list(names)} for name, names in groups]}),
        encoding="utf-8")

    config = cf.ClashConfig(str(path))
    config.apply_results([cf.ProxyTestResult("a", 20), cf.ProxyTestResult("b", 10)],
                         ["自动选择", "自定义"])

    assert config.get_group_proxies("自动选择") == ["b", "a"]
    # 自定义组中未被测试的节点保留，且没有悬空引用
    assert config.get_group_proxies("自定义") == ["a", "custom"]
    assert {p["name"] for p in config.config["proxies"]} == {"a", "b", "custom"}


def test_apply_results_all_failed_leaves_config_untouched(cf, tmp_path):
    nodes = [{"name": "a", "server": "1.1.1.1", "port": 1, "type": "ss",
              "cipher": "aes-256-gcm", "password": "pw"}]
    path = tmp_path / "clash_config.yaml"
    path.write_text(yaml.dump({"proxies": nodes, "proxy-groups": [
        {"name": "自动选择", "type": "url-test", "proxies": ["a"]}]}), encoding="utf-8")

    config = cf.ClashConfig(str(path))
    assert config.apply_results([cf.ProxyTestResult("a", None)], ["自动选择"]) == []
    assert [p["name"] for p in config.config["proxies"]] == ["a"]


def test_save_uses_removesuffix_for_json_path(cf, tmp_path):
    config_path = tmp_path / "clash_config.json"
    config_path.write_text(json.dumps({"proxies": [], "proxy-groups": []}), encoding="utf-8")
    config = cf.ClashConfig(str(config_path))
    config.save()

    # 不能把 .json 后缀里的字符一路 strip 掉
    assert (tmp_path / "clash_config.yaml").exists()
    assert (tmp_path / "clash_config.yaml.json").exists()

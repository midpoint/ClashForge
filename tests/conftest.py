import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _install_stubs():
    """ClashForge 顶层会导入 requests_html / psutil；测试机没装时用最小 stub 顶替"""
    if "requests_html" not in sys.modules:
        try:
            import requests_html  # noqa: F401
        except ImportError:
            module = types.ModuleType("requests_html")

            class HTMLSession:  # pragma: no cover - 仅占位
                def __init__(self, *args, **kwargs):
                    pass

            module.HTMLSession = HTMLSession
            sys.modules["requests_html"] = module

    if "psutil" not in sys.modules:
        try:
            import psutil  # noqa: F401
        except ImportError:
            module = types.ModuleType("psutil")
            module.process_iter = lambda *args, **kwargs: []
            sys.modules["psutil"] = module


@pytest.fixture(scope="session")
def cf():
    """以独立模块名加载 ClashForge.py，避免触发 __main__ 里的真实抓取流程"""
    _install_stubs()
    spec = importlib.util.spec_from_file_location("clashforge_under_test", ROOT / "ClashForge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

import pytest
import types
from unittest.mock import patch, MagicMock
from connectivity import connectivity_telnet

# python



def test_html_escape():
    assert connectivity_telnet.html_escape('<>&"') == '&lt;&gt;&amp;"'

def test_render_html_basic():
    # Minimal fake results
    results = {
        "client1": {
            "meta": {"user": "u", "bastion": None},
            "checks": [
                {"env": "E", "server": "S", "service": "svc", "port": 80, "proto": "tcp", "ok": True},
                {"env": "E", "server": "S", "service": "svc", "port": 81, "proto": "tcp", "ok": False},
            ]
        }
    }
    html = connectivity_telnet.render_html(results)
    assert "Total checks" in html
    assert "client1" in html
    assert "PASS" in html
    assert "FAIL" in html

def test_run_all_checks_calls_tcp_udp(monkeypatch):
    # Patch check_tcp_from_client and check_udp_from_client to always return True/False
    monkeypatch.setattr(connectivity_telnet, "check_tcp_from_client", lambda *a, **kw: True)
    monkeypatch.setattr(connectivity_telnet, "check_udp_from_client", lambda *a, **kw: False)
    # Patch build_clients to return one fake client
    fake_client = connectivity_telnet.Client(host="h", user="u")
    monkeypatch.setattr(connectivity_telnet, "build_clients", lambda: [fake_client])
    # Patch IPA_SERVERS and REQUIRED_PORTS
    monkeypatch.setattr(connectivity_telnet, "IPA_SERVERS", {"ENV": ["srv1"]})
    monkeypatch.setattr(connectivity_telnet, "REQUIRED_PORTS", [("svc", 1, "tcp"), ("svc", 2, "udp")])
    results = connectivity_telnet.run_all_checks()
    assert "h" in results
    checks = results["h"]["checks"]
    assert len(checks) == 2
    assert checks[0]["ok"] is True
    assert checks[1]["ok"] is False

def test_main_writes_files(monkeypatch, tmp_path):
    # Patch run_all_checks and render_html
    fake_results = {"c": {"meta": {}, "checks": []}}
    monkeypatch.setattr(connectivity_telnet, "run_all_checks", lambda: fake_results)
    monkeypatch.setattr(connectivity_telnet, "render_html", lambda r: "<html>stub</html>")
    # Patch OUTPUT_JSON and OUTPUT_HTML to tmp_path
    monkeypatch.setattr(connectivity_telnet, "OUTPUT_JSON", str(tmp_path / "out.json"))
    monkeypatch.setattr(connectivity_telnet, "OUTPUT_HTML", str(tmp_path / "out.html"))
    connectivity_telnet.main()
    assert (tmp_path / "out.json").exists()
    assert (tmp_path / "out.html").exists()
    assert "<html" in (tmp_path / "out.html").read_text()
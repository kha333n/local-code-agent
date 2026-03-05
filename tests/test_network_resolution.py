from __future__ import annotations

from app.utils import network


def test_resolve_ollama_base_url_keeps_explicit_non_local(monkeypatch):
    monkeypatch.setattr(network, "IS_WSL", True)
    resolved = network.resolve_ollama_base_url("http://172.26.176.1:11434")
    assert resolved == "http://172.26.176.1:11434"


def test_resolve_ollama_base_url_in_wsl_uses_default_gateway(monkeypatch):
    monkeypatch.setattr(network, "IS_WSL", True)
    monkeypatch.setattr(network, "_default_gateway_ip", lambda: "172.26.176.1")
    resolved = network.resolve_ollama_base_url("http://127.0.0.1:11434")
    assert resolved == "http://172.26.176.1:11434"


def test_resolve_ollama_base_url_non_wsl_keeps_localhost(monkeypatch):
    monkeypatch.setattr(network, "IS_WSL", False)
    resolved = network.resolve_ollama_base_url("http://127.0.0.1:11434")
    assert resolved == "http://127.0.0.1:11434"


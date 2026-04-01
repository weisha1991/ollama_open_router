import runpy


def test_python_module_entrypoint_calls_router_main(monkeypatch):
    called = {"value": False}

    def fake_main():
        called["value"] = True

    monkeypatch.setattr("ollama_router.router.main", fake_main)

    runpy.run_module("ollama_router", run_name="__main__")

    assert called["value"] is True

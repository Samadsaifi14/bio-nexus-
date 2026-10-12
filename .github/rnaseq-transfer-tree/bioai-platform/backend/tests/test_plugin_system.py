"""Plugin System (Component 20) unit tests — isolated plugin dir, no DB."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.plugin_system import BioNexusPlugin, PluginManager

PLUGIN_SRC = '''
from app.services.plugin_system import BioNexusPlugin

class CheckerA(BioNexusPlugin):
    name = "checker-a"
    version = "1.0.0"
    description = "adds a marker check"

    def on_register(self):
        self.registered = True

    def before_validate(self, engine_name, report, result=None):
        return [{"name": f"{engine_name}:marker", "passed": True, "detail": "plugin check added"}]

    def on_event(self, event, payload):
        return [{"plugin": "checker-a", "event": event}]

class QuietPlugin(BioNexusPlugin):
    name = "quiet"
    version = "0.1.0"
    description = "does nothing"
'''


def _write_plugins(tmp_path) -> Path:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "checkers.py").write_text(PLUGIN_SRC, encoding="utf-8")
    return plugin_dir


def test_discover_and_list(tmp_path):
    manager = PluginManager(str(_write_plugins(tmp_path)))
    loaded = manager.load_dir()
    assert sorted(loaded) == ["checkers"]
    names = {p["name"] for p in manager.list_plugins()}
    assert names == {"checker-a", "quiet"}
    assert all(p["enabled"] for p in manager.list_plugins())


def test_hook_appends_extra_checks(tmp_path):
    manager = PluginManager(str(_write_plugins(tmp_path)))
    manager.load_dir()
    extra = manager.before_validate("blast", {"valid": True})
    assert any(c["name"] == "blast:marker" and c["passed"] for c in extra)


def test_hook_accepts_parsed_result(monkeypatch, tmp_path):
    class FakeResult:
        evidence = {"blast": "hit"}

    manager = PluginManager(str(_write_plugins(tmp_path)))
    manager.load_dir()
    extra = manager.before_validate("blast", {"valid": True}, FakeResult())
    assert any(c["name"] == "blast:marker" and c["passed"] for c in extra)


def test_disable_drops_plugin(tmp_path):
    manager = PluginManager(str(_write_plugins(tmp_path)))
    manager.load_dir()
    assert manager.set_enabled("checker-a", False)
    assert not manager.before_validate("msa", {})
    assert manager.set_enabled("checker-a", True)
    assert any(c["name"] == "msa:marker" for c in manager.before_validate("msa", {}))


def test_unknown_plugin_not_found(tmp_path):
    manager = PluginManager(str(_write_plugins(tmp_path)))
    manager.load_dir()
    assert not manager.set_enabled("ghost", True)


def test_event_records_trace(tmp_path):
    manager = PluginManager(str(_write_plugins(tmp_path)))
    manager.load_dir()
    records = manager.run_event("pipeline_result", {"job_id": "j1"})
    assert any(r.get("plugin") == "checker-a" for r in records)
    assert manager.trace[-1]["event"] == "pipeline_result"


def test_reload_rediscover(tmp_path):
    manager = PluginManager(str(_write_plugins(tmp_path)))
    manager.load_dir()
    manager.set_enabled("checker-a", False)
    reloaded = manager.reload()
    assert reloaded == ["checkers"]
    assert manager.list_plugins()[0]["enabled"] is True


def test_contained_failure(tmp_path):
    src = PLUGIN_SRC.replace('return [{"name": f"{engine_name}:marker", "passed": True, "detail": "plugin check added"}]',
                             'raise RuntimeError("boom")')
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "bad.py").write_text(src, encoding="utf-8")
    manager = PluginManager(str(plugin_dir))
    manager.load_dir()
    # A raising plugin must yield a FAIL check, never an exception.
    extra = manager.before_validate("blast", {})
    assert any(not c["passed"] and "error" in c["name"] for c in extra)


def test_empty_dir(tmp_path):
    manager = PluginManager(str(tmp_path))
    assert manager.load_dir() == []
    assert manager.list_plugins() == []
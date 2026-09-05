"""Plugin System (BioNexus 2.0, Component 20).

Extends the platform at runtime: lightweight Python plugins declare hook
callbacks that are dispatched by the PluginManager around engine validation,
exports and pipeline events. Plugins live in BIONEXUS_PLUGINS_DIR (default
app/plugins/) as plain .py files; each subclass of BioNexusPlugin is loaded,
registered and enabled. All plugin failures are contained (never break the
host operation).
"""

from __future__ import annotations

import importlib.util
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PLUGIN_DIR = os.environ.get("BIONEXUS_PLUGINS_DIR")
if not PLUGIN_DIR:
    PLUGIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")


class BioNexusPlugin:
    """Override the hook methods you care about. `name`/`version` are required."""

    name: str = "unnamed"
    version: str = "0.0.0"
    description: str = ""

    #: lifecycle + pipeline hooks (all optional, all contained-safe)
    def on_register(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def before_validate(self, engine_name: str, report: dict, result: Any = None) -> list[dict]:
        """Return extra validation checks [{name, passed, detail}] appended to
        the engine's native PASS/FAIL report. `result` is the parsed EngineResult."""
        return []

    def after_export(self, engine_name: str, payload: dict) -> dict | None:
        """Optionally decorate an exported artifact (returned dict is merged)."""
        return None

    def on_event(self, event: str, payload: dict) -> list[dict]:
        """Receive arbitrary platform events as a trace record."""
        return []


class PluginManager:
    def __init__(self, plugin_dir: str | None = None) -> None:
        self.dir = plugin_dir or PLUGIN_DIR
        self.plugins: dict[str, BioNexusPlugin] = {}
        self.enabled: set[str] = set()
        self.trace: list[dict] = []
        self._lock = threading.Lock()

    # --- discovery ----------------------------------------------------------

    def load_dir(self, directory: str | None = None) -> list[str]:
        """Import every *.py plugin in the (default) plugin directory."""
        scan_dir = directory or self.dir
        loaded: list[str] = []
        if not os.path.isdir(scan_dir):
            return loaded
        for path in sorted(Path(scan_dir).glob("*.py")):
            if path.name.startswith("_"):
                continue
            before = set(self.plugins)
            self._load_file(path)
            if set(self.plugins) - before:
                loaded.append(path.stem)
        return loaded

    def _load_file(self, path: Path) -> None:
        try:
            spec = importlib.util.spec_from_file_location(f"bionexus_plugin_{path.stem}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:
            logger.warning("plugin %s import failed: %s", path.name, e)
            return
        added = False
        for obj in vars(mod).values():
            if isinstance(obj, type) and issubclass(obj, BioNexusPlugin) and obj is not BioNexusPlugin:
                plugin = obj()
                try:
                    plugin.on_register()
                    self.plugins[plugin.name] = plugin
                    self.enabled.add(plugin.name)
                except Exception as e:
                    logger.warning("plugin %s register failed: %s", plugin.name, e)

    def reload(self) -> list[str]:
        with self._lock:
            self.plugins = {}
            self.enabled = set()
            return self.load_dir()

    # --- state --------------------------------------------------------------

    def list_plugins(self) -> list[dict]:
        with self._lock:
            return [{"name": p.name, "version": p.version, "description": p.description,
                     "enabled": p.name in self.enabled}
                    for p in self.plugins.values()]

    def set_enabled(self, name: str, enabled: bool) -> bool:
        with self._lock:
            if name not in self.plugins:
                return False
            if enabled:
                self.enabled.add(name)
            else:
                self.enabled.discard(name)
                try:
                    self.plugins[name].on_disable()
                except Exception as e:
                    logger.warning("plugin %s on_disable failed: %s", name, e)
            return True

    # --- hooks --------------------------------------------------------------

    def _active(self) -> list[BioNexusPlugin]:
        with self._lock:
            return [p for n, p in self.plugins.items() if n in self.enabled]

    def before_validate(self, engine_name: str, report: dict, result: Any = None) -> list[dict]:
        """Collect extra checks from every active plugin, containing failures."""
        extra: list[dict] = []
        for p in self._active():
            try:
                extra.extend(p.before_validate(engine_name, report, result))
            except Exception as e:
                extra.append({"name": f"{p.name}:validate_error", "passed": False, "detail": str(e)})
        return extra

    def after_export(self, engine_name: str, payload: dict) -> dict:
        merged = dict(payload)
        for p in self._active():
            try:
                decor = p.after_export(engine_name, payload)
                if isinstance(decor, dict):
                    merged.update(decor)
            except Exception as e:
                logger.warning("plugin %s.after_export failed: %s", p.name, e)
        return merged

    def run_event(self, event: str, payload: dict) -> list[dict]:
        records: list[dict] = []
        for p in self._active():
            try:
                records.extend(p.on_event(event, dict(payload)))
            except Exception as e:
                records.append({"plugin": p.name, "event": event, "error": str(e)})
        self.trace.append({"event": event, "payload": payload, "records": records})
        return records


plugin_manager = PluginManager()
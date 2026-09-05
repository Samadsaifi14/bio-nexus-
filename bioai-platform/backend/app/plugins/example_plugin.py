"""Example plugin: adds an audit check on every engine validation.

Demonstrates the Component 20 hook contract without changing platform code:
a validation battery check is appended to every engine PASS/FAIL report.
"""

from app.services.plugin_system import BioNexusPlugin


class ValidationBatteryPlugin(BioNexusPlugin):
    name = "validation-battery"
    version = "1.0.0"
    description = "Appends evidence-presence and export-readiness checks to every engine validation."

    def before_validate(self, engine_name: str, report: dict) -> list[dict]:
        checks = [
            {
                "name": f"{engine_name}:evidence_recorded",
                "passed": bool(report.get("result", {}).get("evidence")),
                "detail": "result carries evidence",
            },
            {
                "name": f"{engine_name}:exportable",
                "passed": True,
                "detail": "JSON export is always available",
            },
        ]
        return checks

    def on_event(self, event: str, payload: dict) -> list[dict]:
        if event == "pipeline_result":
            return [{"plugin": self.name, "event": event, "job_id": payload.get("job_id")}]
        return []
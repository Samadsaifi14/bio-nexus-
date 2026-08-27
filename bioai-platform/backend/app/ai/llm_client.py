import os
import logging
from app.config import settings
from app.ai.prompts import get_prompt

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        # Groq is currently provider-restricted (org_restricted error), so the
        # primary provider is Google Gemini. GROQ_API_KEY is kept only as a
        # possible secondary when it is un-restricted again.
        self.api_key = settings.GOOGLE_API_KEY
        self.fallback_key = settings.GOOGLE_API_KEY
        self.model = settings.DEFAULT_MODEL or "gemini/gemini-3.6-flash"
        self.fallback_model = "gemini/gemini-3.6-flash"
        self.pro_model = settings.PRO_MODEL

    def has_api_key(self) -> bool:
        return bool(self.api_key) or bool(self.fallback_key)

    def get_providers(self) -> list[dict]:
        providers = []
        if self.api_key:
            name = "gemini" if ("gemini/" in self.model or "gemini-" in self.model) else "groq"
            providers.append({"model": self.model, "api_key": self.api_key, "name": name})
        if self.fallback_key:
            providers.append({"model": self.fallback_model, "api_key": self.fallback_key, "name": "gemini"})
        return providers

    def get_all_candidates(self) -> list[dict]:
        """Primary providers plus any explicitly-configured backups, in preference order.

        Used by the streaming interpreter so a rate-limited provider can fall
        back to another model without the user seeing a raw litellm error.

        Only models actually configured in the environment are added — never
        guessed names, and never the built-in PRO_MODEL default (an Anthropic
        model) which would be routed through the Google API key.
        """
        candidates = self.get_providers()
        seen = {(c["model"], c["api_key"]) for c in candidates}
        backups = []
        pro = os.getenv("PRO_MODEL", "").strip()
        if self.fallback_key and pro:
            if (pro, self.fallback_key) not in seen:
                backups.append({"model": pro, "api_key": self.fallback_key, "name": "gemini-fallback"})
                seen.add((pro, self.fallback_key))
        return candidates + backups

    def build_prompt(self, pipeline_type: str, context: dict) -> str:
        template = get_prompt(pipeline_type)
        blast = context.get("blast", {})
        top = blast.get("top_hit", {})
        uniprot = context.get("uniprot", {}) or {}
        af = context.get("alphafold", {}) or {}

        values = {
            "blast_count": blast.get("count", 0),
            "top_hit_accession": top.get("accession", "N/A"),
            "top_hit_description": top.get("description", "N/A"),
            "top_hit_evalue": top.get("evalue", "N/A"),
            "top_hit_identity_pct": top.get("identity_pct", "N/A"),
            "top_hit_bit_score": top.get("bit_score", "N/A"),
            "uniprot_name": uniprot.get("full_name", "N/A"),
            "uniprot_organism": uniprot.get("organism", "N/A"),
            "uniprot_genes": ", ".join(uniprot.get("gene_names", []) or []) or "N/A",
            "uniprot_functions": "; ".join(uniprot.get("functions", []) or []) or "N/A",
            "uniprot_locations": "; ".join(uniprot.get("subcellular_locations", []) or []) or "N/A",
            "uniprot_keywords": ", ".join(uniprot.get("keywords", []) or []) or "N/A",
            "uniprot_go_terms": ", ".join(uniprot.get("go_terms", []) or []) or "N/A",
            "uniprot_features": "; ".join(
                f"{f.get('type', '')}: {f.get('description', '')}" for f in (uniprot.get("features", []) or [])
            ) or "N/A",
            "alphafold_available": "Yes" if af.get("structure_available") else "No",
            "alphafold_confidence": af.get("confidence", "N/A"),
        }

        # Live API text (BLAST descriptions, UniProt functions…) can contain
        # { or } characters, which str.format() would try to interpret as
        # placeholders and crash the prompt build. Escape them in every value.
        escaped = {k: _format_safe(v) for k, v in values.items()}
        try:
            return template.format(**escaped)
        except Exception as e:  # last-resort: never let prompt build break the pipeline
            logger.warning("Prompt template %s failed to fill (%s); using fallback prompt", pipeline_type, e)
            return (
                f"Analyze this protein. BLAST top hit: {values['top_hit_description']} "
                f"(E-value {values['top_hit_evalue']}, identity {values['top_hit_identity_pct']}%). "
                f"UniProt: {values['uniprot_name']} from {values['uniprot_organism']}. "
                f"Functions: {values['uniprot_functions']}."
            )


def _format_safe(value) -> str:
    """Escape braces so API-returned text cannot corrupt a str.format() template."""
    return str(value).replace("{", "{{").replace("}", "}}")


llm_client = LLMClient()

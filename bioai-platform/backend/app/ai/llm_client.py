import os
import logging
from app.config import settings
from app.ai.prompts import get_prompt

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.fallback_key = settings.GOOGLE_API_KEY
        self.model = settings.DEFAULT_MODEL
        self.fallback_model = "gemini/gemini-2.0-flash"
        self.pro_model = settings.PRO_MODEL

    def has_api_key(self) -> bool:
        return bool(self.api_key) or bool(self.fallback_key)

    def get_providers(self) -> list[dict]:
        providers = []
        if self.api_key:
            providers.append({"model": self.model, "api_key": self.api_key, "name": "groq"})
        if self.fallback_key:
            providers.append({"model": self.fallback_model, "api_key": self.fallback_key, "name": "gemini"})
        return providers

    def get_all_candidates(self) -> list[dict]:
        """Primary providers plus any configured backups, in preference order.

        Used by the streaming interpreter so a rate-limited provider can fall
        back to another model without the user seeing a raw litellm error.
        """
        candidates = self.get_providers()
        seen = {(c["model"], c["api_key"]) for c in candidates}
        backups = []
        if self.fallback_key:
            backup_models = []
            if self.pro_model and self.pro_model != self.fallback_model:
                backup_models.append(self.pro_model)
            backup_models.append("gemini/gemini-1.5-flash")
            for model in backup_models:
                if (model, self.fallback_key) not in seen:
                    backups.append({"model": model, "api_key": self.fallback_key, "name": "gemini-fallback"})
                    seen.add((model, self.fallback_key))
        return candidates + backups

    def build_prompt(self, pipeline_type: str, context: dict) -> str:
        template = get_prompt(pipeline_type)
        blast = context.get("blast", {})
        top = blast.get("top_hit", {})
        uniprot = context.get("uniprot", {}) or {}
        af = context.get("alphafold", {}) or {}

        return template.format(
            blast_count=blast.get("count", 0),
            top_hit_accession=top.get("accession", "N/A"),
            top_hit_description=top.get("description", "N/A"),
            top_hit_evalue=top.get("evalue", "N/A"),
            top_hit_identity_pct=top.get("identity_pct", "N/A"),
            top_hit_bit_score=top.get("bit_score", "N/A"),
            uniprot_name=uniprot.get("full_name", "N/A"),
            uniprot_organism=uniprot.get("organism", "N/A"),
            uniprot_genes=", ".join(uniprot.get("gene_names", []) or []) or "N/A",
            uniprot_functions="; ".join(uniprot.get("functions", []) or []) or "N/A",
            uniprot_locations="; ".join(uniprot.get("subcellular_locations", []) or []) or "N/A",
            uniprot_keywords=", ".join(uniprot.get("keywords", []) or []) or "N/A",
            uniprot_go_terms=", ".join(uniprot.get("go_terms", []) or []) or "N/A",
            uniprot_features="; ".join(
                f"{f.get('type', '')}: {f.get('description', '')}" for f in (uniprot.get("features", []) or [])
            ) or "N/A",
            alphafold_available="Yes" if af.get("structure_available") else "No",
            alphafold_confidence=af.get("confidence", "N/A"),
        )


llm_client = LLMClient()

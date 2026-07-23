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

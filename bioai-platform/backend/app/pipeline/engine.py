from typing import Any
from app.pipeline.registry import registry
from app.pipeline.assembler import ContextAssembler
from app.tools.blast import BlastTool
from app.tools.uniprot import UniprotTool
from app.tools.alphafold import AlphaFoldTool


class PipelineEngine:
    def __init__(self):
        self.assembler = ContextAssembler()
        self.blast_tool = BlastTool()
        self.uniprot_tool = UniprotTool()
        self.alphafold_tool = AlphaFoldTool()

    async def execute(self, sequence: str, database: str = "uniprotkb_swissprot", max_hits: int = 10) -> dict:
        blast_result = await self.blast_tool.run({
            "sequence": sequence,
            "database": database,
            "max_hits": max_hits,
        })

        if "error" in blast_result:
            return {"error": blast_result["error"], "steps_completed": []}

        top_accession = ""
        if blast_result.get("hits"):
            top_accession = blast_result["hits"][0].get("accession", "")

        uniprot_result = None
        if top_accession:
            uniprot_result = await self.uniprot_tool.run({"accession": top_accession})

        alphafold_result = None
        if top_accession and uniprot_result and "error" not in uniprot_result:
            alphafold_result = await self.alphafold_tool.run({"uniprot_accession": top_accession})

        context = self.assembler.assemble(sequence, blast_result, uniprot_result, alphafold_result)

        return {
            "context": context,
            "steps_completed": ["blast", "uniprot", "alphafold"],
            "blast_raw": blast_result,
            "uniprot_raw": uniprot_result,
            "alphafold_raw": alphafold_result,
        }

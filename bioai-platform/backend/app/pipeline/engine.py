import asyncio
import logging
from typing import Callable, List, Optional, Any

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[str, List[str], int], Any]]


class PipelineEngine:
    def __init__(self):
        from app.tools.blast import BlastTool
        from app.tools.uniprot import UniprotTool
        from app.tools.alphafold import AlphaFoldTool
        from app.pipeline.assembler import ContextAssembler

        self.blast = BlastTool()
        self.uniprot = UniprotTool()
        self.alphafold = AlphaFoldTool()
        self.assembler = ContextAssembler()

    async def execute(
        self,
        job_id: str,
        sequence: str,
        pipeline_type: str = "protein_analysis",
        database: str = "uniprotkb_swissprot",
        max_hits: int = 10,
        progress_callback: ProgressCallback = None,
    ) -> dict:
        steps_completed: List[str] = []

        async def _tick(step: str, pct: int) -> None:
            steps_completed.append(step)
            if progress_callback:
                try:
                    result = progress_callback(job_id, list(steps_completed), pct)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.warning(f"[{job_id}] Progress callback error (ignored): {e}")

        logger.info(f"[{job_id}] Step 1/3: BLAST")
        blast_result = await self.blast.run({
            "sequence": sequence,
            "database": database,
            "max_hits": max_hits,
        })
        await _tick("blast", 33)

        hits: list = blast_result.get("hits") or []
        top_accession: Optional[str] = hits[0].get("accession") if hits else None

        logger.info(f"[{job_id}] Step 2/3: UniProt (accession={top_accession})")
        uniprot_result = (
            await self.uniprot.run({"accession": top_accession}) if top_accession else None
        )
        await _tick("uniprot", 66)

        logger.info(f"[{job_id}] Step 3/3: AlphaFold (accession={top_accession})")
        alphafold_result = (
            await self.alphafold.run({"uniprot_accession": top_accession}) if top_accession else None
        )
        await _tick("alphafold", 90)

        logger.info(f"[{job_id}] Assembling context")
        context = self.assembler.assemble(
            sequence,
            blast_result,
            uniprot_result,
            alphafold_result,
        )

        if hasattr(context, "model_dump"):
            return context.model_dump()
        if hasattr(context, "dict"):
            return context.dict()
        if not isinstance(context, dict):
            return dict(context)
        return context

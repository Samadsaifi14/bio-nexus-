from app.tools.blast import BlastTool
from app.tools.uniprot import UniprotTool
from app.tools.alphafold import AlphaFoldTool
from app.pipeline.registry import registry


def register_all_tools():
    registry.register(BlastTool())
    registry.register(UniprotTool())
    registry.register(AlphaFoldTool())

# BioNexus Scientific Engines

> Generated — do not edit by hand.

## alphafold

- **Version:** 1.0.0
- **Tool:** AlphaFold (version detected at runtime)
- **Databases:** AlphaFold DB
- **Parameters:** {'lookup': 'AlphaFold DB by UniProt accession', 'de_novo': 'ESMFold ab initio when resolution is unavailable', 'confidence_metric': 'mean pLDDT (0-100)'}
- **Benchmarks:** PDB_TP53_STRUCTURE_AVAILABLE, ALPHAFOLD_TP53_AVAILABLE, ALPHAFOLD_INSULIN_AVAILABLE
- **Exports:** json, csv
- **Figures:** svg

- **Citations:**
  - Jumper J, et al. Highly accurate protein structure prediction with AlphaFold. Nature 596:583-589, 2021.
  - Varadi M, et al. AlphaFold Protein Structure Database in 2024. Nucleic Acids Res 52:D368-D375, 2024.
  - Lin Z, et al. Evolutionary-scale prediction of atomic-level protein structure with a language model. Science 379:1123-1130, 2023.

## blast

- **Version:** 1.0.0
- **Tool:** BLAST (version detected at runtime)
- **Databases:** nr, swissprot, pdb, pdb_nr, refseq_protein, env_nr, nt, refseq_rna
- **Parameters:** {'program': ['blastp', 'blastn', 'blastx', 'tblastn'], 'max_hits': '5-100', 'fallback_rule': 'EBI first, then NCBI'}
- **Benchmarks:** INSULIN_SWISSPROT_TOP_HIT, HUMAN_TP53_SWISSPROT_TOP_HIT, HUMAN_TP53_NOT_INSULIN, HUMAN_OXTR_SWISSPROT_TOP_HIT, HUMAN_HBB_SWISSPROT_TOP_HIT
- **Exports:** json, csv
- **Figures:** svg

- **Citations:**
  - Altschul S.F. et al. Basic Local Alignment Search Tool. J Mol Biol 215(3):403-410, 1990.
  - Camacho C. et al. BLAST+: architecture and applications. BMC Bioinformatics 10:421, 2009.
  - Madeira F. et al. Search and sequence analysis tools services from EMBL-EBI in 2022. Nucleic Acids Res, 2022.

## docking

- **Version:** 1.0.0
- **Tool:** AutoDock Vina (with interaction profiling) (version detected at runtime)
- **Databases:** PDB/receptor (from structure stage)
- **Parameters:** {'search': 'AutoDock Vina (exhaustiveness/num_modes)', 'rescoring': 'optional Gnina CNN rescoring (graceful fallback)', 'interactions': 'H-bonds, hydrophobic, pi stacking, salt bridges from PDB ligand pose', 'affinity_window_kcal_mol': [-60.0, 30.0]}
- **Benchmarks:** DOCKING_P53_APRIL_VINA_AFFINITY_BOUNDED
- **Exports:** json, csv
- **Figures:** svg

- **Citations:**
  - Trott O, Olson AJ. AutoDock Vina: improving the speed and accuracy of docking. J Comput Chem 31:455-461, 2010.
  - Lu J, et al. Universal and efficient ligand binding pose prediction. Nat Protoc (Gnina rescoring) 2024.

## domains

- **Version:** 1.0.0
- **Tool:** InterPro (version detected at runtime)
- **Databases:** InterPro (Pfam, SMART, PROSITE, CDD, PANTHER, PRINTS, HAMAP)
- **Parameters:** {'lookup': 'InterPro entry lookup by UniProt accession', 'output': 'domain architecture: db, name, start, end, score'}
- **Benchmarks:** DOMAINS_ANNOTATED, DOMAINS_GEOMETRY_VALID
- **Exports:** json, csv
- **Figures:** svg

- **Citations:**
  - Paysan-Lafosse T, et al. InterPro in 2022. Nucleic Acids Res 51:D418-D427, 2023.
  - Mistry J, et al. Pfam: The protein families database in 2021. Nucleic Acids Res 49:D412-D419, 2021.
  - de Castro E, et al. ScanProsite: detection of PROSITE signature matches. Nucleic Acids Res 34:W362-W365, 2006.

## evidence

- **Version:** 1.0.0
- **Tool:** Evidence Graph (version detected at runtime)
- **Databases:** derived from provenance graph
- **Parameters:** {'input': 'evidence graph: sources + claims + edges', 'source_identity': 'static tool/database/version map per result section', 'claim_linking': 'keyword overlap between sentence and source vocabulary', 'confidence': 'high (2+ sources) / medium (1) / low (0)', 'honesty': 'unsupported claims are marked rejected, never hidden'}
- **Benchmarks:** 
- **Exports:** json, csv
- **Figures:** svg

- **Citations:**
  - BioNexus AI Evidence Engine — claim-to-source provenance for AI interpretations.
  - Wright K, et al. The Future of Clinical AI: Explainability. Nat Rev Nephrol 2021.

## interpret

- **Version:** 1.0.0
- **Tool:** LLM interpretation (version detected at runtime)
- **Databases:** 
- **Parameters:** {'provider_chain': 'Groq -> Gemini -> Ollama (fallback, retries)', 'temperature': 0.3, 'max_tokens': 2000, 'honesty': 'failure yields an explicit banner, never fabricated analysis'}
- **Benchmarks:** 
- **Exports:** json, txt
- **Figures:** svg

- **Citations:**
  - BioNexus honest-AI acceptance criteria (MASTER_PLAN): an unexecuted or failed LLM pass displays a visible banner, never fake analysis.

## md

- **Version:** 1.0.0
- **Tool:** OpenMM simulation + BioPython structural analysis (version detected at runtime)
- **Databases:** structure (PDB atom coordinates)
- **Parameters:** {'forcefields': ['amber14', 'charmm', 'gromacs'], 'solvents': ['explicit-tip3p', 'explicit-tip4pew', 'implicit-gbn2'], 'report': 'RMSD / Rg / SASA / energy over trajectories'}
- **Benchmarks:** MD_RMSD_AVG_NONNEGATIVE
- **Exports:** json, csv
- **Figures:** svg

- **Citations:**
  - Eastman P, et al. OpenMM 8: Molecular dynamics simulation with machine learning potentials. J Phys Chem B 2024.
  - Cock PJ, et al. Biopython. Bioinformatics 25:1422-1423, 2009.

## msa

- **Version:** 1.0.0
- **Tool:** MSA (version detected at runtime)
- **Databases:** SWISS-PROT homologs
- **Parameters:** {'methods': ['mafft-local', 'EBI ClustalO/MAFFT/Kalign/MUSCLE/T-Coffee', 'in-process fallback'], 'mode': 'global (or local refinement of the top hit)', 'selection': 'top 5 BLAST hits + query'}
- **Benchmarks:** MSA_VALID_ALIGNMENT, MSA_ALIGNMENT_METHOD_RECORDED, MSA_HEMOGLOBIN_ALIGNMENT_LENGTH
- **Exports:** json, csv, fasta
- **Figures:** svg

- **Citations:**
  - Katoh K, Standley DM. MAFFT Multiple Sequence Alignment Software Version 7. Mol Biol Evol 30:772-780, 2013.
  - Sievers F, Higgins DG. Clustal Omega for making accurate alignments of many protein sequences. Protein Sci 27:135-145, 2018.
  - Madeira F, et al. Search and sequence analysis tools services from EMBL-EBI in 2022. Nucleic Acids Res 50:W276-W279, 2022.

## ngs

- **Version:** 1.0.0
- **Tool:** NGS production pipeline (manual mode / Sarek-style DAG) (version detected at runtime)
- **Databases:** FASTQ (interpretation), grch38/hg38
- **Parameters:** {'stages': 'FastQC -> MultiQC(anomaly) -> alignment QC -> variant calling -> normalization -> QC -> filtering', 'qc_thresholds': {'q30_min': 80.0, 'gc_range': [0, 100], 'mapping_min': 0.5}, 'demo_profiles': ['tumor-exome', 'germline-wgs', 'rna-tumor', 'humanized'], 'input_note': 'raw results are a compact demonstration/positive control unless all_records_processed'}
- **Benchmarks:** NGS_FASTQC_Q30_ABOVE_THRESHOLD
- **Exports:** json, csv
- **Figures:** svg

- **Citations:**
  - Andrews S. FastQC: A Quality Control tool for High Throughput Sequence Data. Babraham Bioinformatics.
  - Li H. Aligning sequence reads, clone sequences and assembly contigs with BWA-MEM. arXiv:1303.3997, 2013.
  - Van der Auwera GA, O'Connor BD. Genomics in the Cloud. O'Reilly, 2020 (GATK best practices).

## pathway

- **Version:** 1.0.0
- **Tool:** Reactome (version detected at runtime)
- **Databases:** Reactome
- **Parameters:** {'method': 'over-representation analysis (ORA)', 'stats': 'p-value / FDR reported exactly as supplied by Reactome Analysis Service', 'input': 'top UniProt gene names (max 20)'}
- **Benchmarks:** 
- **Exports:** json, csv
- **Figures:** svg

- **Citations:**
  - Gillespie M, et al. The reactome pathway knowledgebase 2022. Nucleic Acids Res 50:D687-D692, 2022.
  - Fabregat A, et al. Reactome pathway analysis: a high-performance in-memory approach. BMC Bioinformatics 18:142, 2017.

## phylo

- **Version:** 1.0.0
- **Tool:** Newick phylo (EBI ClustalO guide tree) (version detected at runtime)
- **Databases:** SWISS-PROT homologs
- **Parameters:** {'method': 'guide tree from EBI MSA (Clustal Omega)', 'input': 'phylotree produced by the MSA stage', 'notes': 'topology-only rendering; branch lengths are not drawn'}
- **Benchmarks:** PHYLO_GLOBIN_NEWICK_WELLFORMED
- **Exports:** json, csv, newick
- **Figures:** svg

- **Citations:**
  - Sievers F, Higgins DG. Clustal Omega for making accurate alignments of many protein sequences. Protein Sci 27:135-145, 2018.
  - Felsenstein J. PHYLIP - Phylogeny Inference Package. Cladistics 5:164-166, 1989.
  - Madeira F, et al. Search and sequence analysis tools services from EMBL-EBI in 2022. Nucleic Acids Res 50:W276-W279, 2022.

## uniprot

- **Version:** 1.0.0
- **Tool:** UniProt (version detected at runtime)
- **Databases:** UniProtKB/Swiss-Prot, UniProtKB/TrEMBL
- **Parameters:** {'fields': ['accession', 'full_name', 'organism', 'gene_names', 'functions', 'go_terms', 'keywords', 'subcellular_locations', 'pdb_ids', 'features'], 'resolution_ladder': 'direct -> xref -> name search -> EBI sequence BLAST -> idmapping', 'confidence_levels': ['identified', 'homolog']}
- **Benchmarks:** UNIPROT_TP53_RETRIEVAL, UNIPROT_INSULIN_RETRIEVAL, UNIPROT_OXTR_RETRIEVAL, UNIPROT_PSA_RETRIEVAL, UNIPROT_P53_MUST_BE_TP53_GENE
- **Exports:** json, csv
- **Figures:** svg

- **Citations:**
  - UniProt Consortium. UniProt: the Universal Protein Knowledgebase in 2023. Nucleic Acids Res 51:D523-D531, 2023.
  - Ashburner M. et al. Gene Ontology: tool for the unification of biology. Nat Genet 25:25-29, 2000.
  - The Gene Ontology Consortium. The Gene Ontology resource: enriching a GOld mine. Nucleic Acids Res 49:D325-D334, 2021.

'use client';

import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { fadeUp } from '@/lib/animations';
import { BackButton, CriticalButton, PageHeader } from '@/components/ui';

type Section = {
  heading: string;
  content: string;
  code?: string;
};

type TopicData = {
  title: string;
  description: string;
  sections: Section[];
};

const topics: Record<string, TopicData> = {
  blast: {
    title: 'BLAST Search',
    description: 'Basic Local Alignment Search Tool — the most widely used method for finding sequence similarity.',
    sections: [
      {
        heading: 'What is BLAST?',
        content: 'BLAST compares a query sequence against a database of sequences and finds regions of local similarity. It uses a heuristic approach that is much faster than full dynamic programming (Smith-Waterman) while remaining sensitive enough for most searches. BLAST comes in several variants: BLASTP (protein-protein), BLASTN (nucleotide-nucleotide), BLASTX (translated nucleotide query against protein database), TBLASTN (protein query against translated nucleotide database), and TBLASTX (translated nucleotide against translated nucleotide).',
      },
      {
        heading: 'How to read E-values',
        content: 'The E-value (Expect value) describes how many matches you would expect to see by chance when searching a database of a given size. A lower E-value means a more significant match. An E-value of 0.05 means there is a 5% chance of seeing that match by chance alone. A good rule of thumb: E-values below 1e-5 (0.00001) are typically considered significant for homology searches. Values between 0.001 and 0.1 may indicate distant homology and should be investigated further.',
        code: 'E-value = K × m × n × e^(−λS)\n\n  K = search-space constant\n  m = query length\n  n = database length\n  S = raw alignment score\n  λ = scoring-system lambda',
      },
      {
        heading: 'Understanding bit scores',
        content: 'The bit score is a normalized, log-scaled version of the raw alignment score. It is independent of database size and scoring matrix, making it comparable across different searches. A bit score of 50 or higher typically indicates a biologically relevant match. Bit scores are calculated as S\' = (λS − ln K) / ln 2, where S is the raw score, λ and K are statistical parameters of the scoring system.',
      },
      {
        heading: 'Interpreting identity percentage',
        content: 'Percent identity is simply the fraction of aligned positions where the residues match exactly, expressed as a percentage. It is the most intuitive metric but can be misleading for divergent sequences. For proteins, 30% identity over a full-length alignment is often considered the "twilight zone" below which inferring homology becomes unreliable. However, short regions of high identity can be functionally significant even when overall identity is low.',
      },
    ],
  },
  alignment: {
    title: 'Sequence Alignment',
    description: 'Comparing sequences to identify regions of similarity — the foundation of bioinformatics.',
    sections: [
      {
        heading: 'Pairwise vs Multiple Alignment',
        content: 'Pairwise alignment compares two sequences at a time. It can be global (Needleman-Wunsch) which aligns the entire length of both sequences, or local (Smith-Waterman) which finds the best matching subsequence. Multiple sequence alignment (MSA) extends this to three or more sequences, revealing conserved regions across a family. Common MSA tools include Clustal Omega, MAFFT, and MUSCLE. MSA is the basis for building phylogenetic trees, identifying conserved motifs, and improving structure prediction.',
      },
      {
        heading: 'Scoring matrices',
        content: 'Scoring matrices define the score for aligning any two residues. BLOSUM (BLOcks SUbstitution Matrix) matrices are the most common for proteins. BLOSUM62 is the default for most searches — it assumes sequences with ~62% identity. Higher numbers (BLOSUM80) are better for closely related sequences; lower numbers (BLOSUM45) are better for distantly related ones. For nucleotides, simple match/mismatch scores are typically used (e.g., +1/-1 or +2/-3).',
        code: 'BLOSUM62 example (positive scores = conserved substitutions):\n\n     A   R   N   D   C   Q   E   G ...\n  A  4  -1  -2  -2   0  -1  -1   0\n  R -1   5   0  -2  -3   1   0  -2\n  N -2   0   6   1  -3   0   0   0\n  D -2  -2   1   6  -3   0   2  -1',
      },
      {
        heading: 'Gap penalties',
        content: 'Gap penalties control the cost of inserting gaps in an alignment. They consist of two components: a gap-open penalty (cost for starting a gap) and a gap-extension penalty (cost for extending an existing gap). Typical values for protein alignments are 10-12 for opening and 1-2 for extension. High gap penalties produce shorter, more compact alignments; low penalties allow longer gaps but risk over-fitting.',
      },
      {
        heading: 'Reading alignment output',
        content: 'Standard alignment output uses a three-line format for each block: the query sequence, a match line showing identical (|), conserved (:), and gap ( ) symbols, and the subject sequence. Identical residues indicate perfect conservation; conserved substitutions (similar biochemical properties) are shown with colons; non-conserved substitutions have no symbol. Gaps introduced in either sequence are shown as dashes.',
        code: 'Query:   MKLLVLFLLGLVALSECDIYNYNA...KLCGVL\n                ||:||| || | ::|.||:  ...||:..|\nSubject: MKLLILFLLGLVALLLCEPSLYNYNA...NYCTAL',
      },
    ],
  },
  domains: {
    title: 'Domain Analysis',
    description: 'Identifying conserved functional and structural units within proteins.',
    sections: [
      {
        heading: 'What are protein domains?',
        content: 'A protein domain is a conserved, independently folding region of a protein that carries a specific function. Domains are the evolutionary building blocks of proteins — they can be shuffled, duplicated, and combined in different arrangements to create proteins with new functions. Most eukaryotic proteins contain multiple domains. Identifying domains helps predict protein function, even when the overall sequence has no known homologs.',
      },
      {
        heading: 'Pfam and InterPro',
        content: 'Pfam is a comprehensive database of protein domain families, each represented by a multiple sequence alignment and a hidden Markov model (HMM) profile. InterPro combines multiple domain databases (Pfam, SMART, PROSITE, CDD, etc.) into a single resource. When you run a domain analysis, your query is scanned against these HMM profiles to identify known domains. Each hit includes an E-value, bitscore, and the region of the query that matches the domain model.',
      },
      {
        heading: 'Domain architecture',
        content: 'Domain architecture refers to the linear arrangement of domains along a protein sequence. Many proteins have a modular architecture where different domains work together. For example, a signaling protein might have a receptor domain, a kinase domain, and a protein-protein interaction domain. Analyzing domain architecture helps predict function, evolutionary relationships, and potential interactions with other proteins.',
        code: 'Example domain architecture:\n\n  Protein: EGFR (Epidermal Growth Factor Receptor)\n  \n  [Receptor L]──[Furin-like]──[GF_recep]──[TM]──[PKinase_Tyr]\n      |              |             |       |         |\n   Ligand-binding    |          Growth    Trans-   Tyrosine\n   (extracellular)   |          factor    membrane  kinase\n                  Cysteine-rich   rec.               (cytoplasmic)\n                  domain        domain',
      },
    ],
  },
  phylo: {
    title: 'Phylogenetic Trees',
    description: 'Reconstructing evolutionary relationships from molecular sequences.',
    sections: [
      {
        heading: 'Phylogenetic trees',
        content: 'A phylogenetic tree is a branching diagram showing the evolutionary relationships among species, genes, or sequences. Trees consist of branches (edges) and nodes (branch points). Terminal nodes (leaves) represent extant sequences; internal nodes represent hypothetical ancestors. Trees can be rooted (with a known common ancestor) or unrooted. The topology describes the branching order, while branch lengths typically represent evolutionary distance.',
      },
      {
        heading: 'NJ vs UPGMA vs Maximum Likelihood',
        content: 'Neighbor-Joining (NJ) is a fast distance-based method that builds a tree by iteratively joining the closest pair of sequences. UPGMA is another distance method that assumes a constant molecular clock (same rate across all lineages). Maximum Likelihood (ML) is a more sophisticated method that evaluates different tree topologies and selects the one that makes the sequence data most likely under a given substitution model. ML is slower but more accurate. Modern ML tools include RAxML-NG, IQ-TREE, and PhyML.',
      },
      {
        heading: 'Reading bootstrap values',
        content: 'Bootstrap values indicate how strongly the data supports a given branch. The original sequences are resampled (with replacement) hundreds or thousands of times, a tree is built from each replicate, and the fraction of replicates that recover the same branch is the bootstrap value. Values above 70% are considered moderately supported; above 95% is strongly supported. Bootstrap values below 50% suggest the branching order at that node is unreliable.',
        code: 'Example tree with bootstrap values:\n\n                   ┌─── Human\n         ┌─── 98 ──┤\n         │         └─── Chimp\n    ── 100 ─┤\n         │         ┌─── Mouse\n         └─── 72 ──┤\n                   └─── Rat\n\n  100 = very strong support for human/chimp clade\n  72  = moderate support for mouse/rat clade',
      },
      {
        heading: 'Branch lengths',
        content: 'Branch lengths represent the amount of evolutionary change along a branch. The units are typically substitutions per site — the expected number of residue changes per position along that lineage. Longer branches mean more divergence. In distance-based trees, branch lengths are additive: the distance between two sequences is the sum of branch lengths along the path connecting them. In ML trees, branch lengths are optimized to maximize the likelihood of the data.',
      },
    ],
  },
  structure: {
    title: 'Protein Structure',
    description: 'Understanding the three-dimensional shapes of proteins and how to analyze them.',
    sections: [
      {
        heading: 'PDB format',
        content: 'The Protein Data Bank (PDB) format is the standard file format for macromolecular structures. Each line in a PDB file contains specific information identified by a record type (ATOM, HETATM, HELIX, SHEET, etc.). The ATOM records contain the coordinates (x, y, z) of each atom, along with the atom name, residue name, chain identifier, residue number, and occupancy/temperature factors. Modern alternatives include mmCIF and PDBx/mmCIF, but PDB remains widely supported.',
        code: 'Example PDB ATOM record:\n\nATOM      1  N   ALA A   1      21.894  16.287   5.352  1.00  9.58           N\nATOM      2  CA  ALA A   1      22.482  15.026   5.846  1.00  9.74           C\nATOM      3  C   ALA A   1      23.176  14.242   4.744  1.00  9.46           C\nATOM      4  O   ALA A   1      23.121  14.636   3.579  1.00  9.22           O\n\nCol 1-6: Record name\nCol 7-11: Serial number\nCol 13-16: Atom name\nCol 18-20: Residue name\nCol 22: Chain ID\nCol 23-26: Residue number\nCol 31-38: X coordinate\nCol 39-46: Y coordinate\nCol 47-54: Z coordinate',
      },
      {
        heading: 'AlphaFold',
        content: 'AlphaFold is a deep learning system developed by DeepMind that predicts protein structures from amino acid sequences with accuracy comparable to experimental methods. AlphaFold2 won the CASP14 competition in 2020. Its successor, AlphaFold3, extends predictions to protein-ligand, protein-nucleic acid, and protein-small molecule complexes. The AlphaFold Database contains over 200 million predicted protein structures covering nearly all known proteins.',
      },
      {
        heading: 'Reading pLDDT scores',
        content: 'pLDDT (predicted Local Distance Difference Test) is AlphaFold\'s per-residue confidence score, ranging from 0 to 100. A pLDDT above 90 indicates very high confidence (comparable to experimental structures). Values between 70 and 90 indicate good backbone prediction. Values between 50 and 70 indicate low confidence, and below 50 indicates very low confidence — likely unstructured or disordered regions. The pLDDT score is stored in the B-factor column of the PDB file in AlphaFold predictions.',
        code: 'pLDDT confidence interpretation:\n\n  > 90  — Very high (comparable to experiment)\n  70–90 — Good backbone prediction\n  50–70 — Low confidence\n  < 50  — Very low (likely disordered)',
      },
      {
        heading: 'Structure visualization',
        content: 'Protein structures can be visualized in several representations: cartoon/ribbon (shows secondary structure), surface (shows solvent-accessible surface), sticks (shows atomic bonds), and spheres (space-filling). Web-based viewers like Mol* (MolStar), NGL Viewer, and 3Dmol.js enable interactive visualization directly in the browser. Synteny uses Mol* for structure rendering, supporting PDB and mmCIF files with customizable color schemes and selection highlighting.',
      },
    ],
  },
  function: {
    title: 'Function Prediction',
    description: 'Predicting what a protein does from its sequence and structure using Gene Ontology terms.',
    sections: [
      {
        heading: 'The Gene Ontology',
        content: 'The Gene Ontology (GO) is a standardized vocabulary describing three independent aspects of biology: molecular function (MF — what the protein does, e.g. kinase activity), biological process (BP — the larger process it participates in, e.g. DNA repair), and cellular component (CC — where it acts, e.g. nucleus). Every protein can carry multiple GO annotations across all three namespaces, making GO the universal language for describing and comparing protein function.',
      },
      {
        heading: 'GO terms and evidence',
        content: 'Each GO annotation is a term (e.g. GO:0005515 "protein binding") linked to a source of evidence. Curated evidence codes (IDA, IMP, TAS, IC) come from experiments and direct curator review, while computational codes (IEA, ISS) are inferred electronically or from sequence similarity. Predictions from deep-learning models are computational evidence: useful for hypothesis generation, but never a substitute for experimental validation. Synteny flags the method behind every predicted term (e.g. "heuristic composition") so its weight is clear.',
      },
      {
        heading: 'Confidence scores',
        content: 'Synteny assigns each predicted GO term a confidence from 0 to 1 based on how strong the underlying compositional signal is. Confidence above 0.8 is labeled High, 0.6–0.8 Medium, and below 0.6 Low (treated as tentative). These are model confidences, not statistical significance — treat low-confidence predictions as leads to test, not conclusions.',
      },
      {
        heading: 'EC numbers',
        content: 'EC (Enzyme Commission) numbers classify enzymes by the reaction they catalyze, e.g. EC 2.7.1.1 (hexokinase, a transferase). The hierarchy is: class (1 oxidoreductases, 2 transferases, 3 hydrolases, 4 lyases, 5 isomerases, 6 ligases) → subclass → sub-subclass → serial number. The current heuristic model does not predict EC numbers; enzyme classification is out of scope until a full model is deployed.',
      },
      {
        heading: 'DeepFRI and graph models',
        content: 'DeepFRI (Deep Functional Residue Identification) is a state-of-the-art graph convolutional network that predicts GO terms and EC numbers directly from protein structures, using the protein contact map as a graph and its sequence as node features. It substantially outperforms sequence-only methods and even annotates functions that sequence homology cannot detect. Synteny ships a lightweight, composition-based approximation inspired by DeepFRI; deploying the full DeepFRI weights is the planned production upgrade.',
      },
    ],
  },
  pathways: {
    title: 'Pathway Analysis',
    description: 'Mapping genes and proteins to the biological pathways they participate in.',
    sections: [
      {
        heading: 'What are pathways?',
        content: 'A biological pathway is a series of molecular interactions and reactions that produce a specific cellular outcome. Metabolic pathways involve chemical transformations (e.g., glycolysis, citric acid cycle). Signaling pathways transmit signals from the cell surface to the nucleus (e.g., MAPK/ERK, Wnt). Gene regulatory pathways control gene expression. Pathway analysis helps interpret high-throughput data (RNA-seq, proteomics) by identifying which pathways are enriched in a set of differentially expressed genes.',
      },
      {
        heading: 'Reactome vs KEGG',
        content: 'Reactome is a free, open-source, manually curated pathway database with detailed molecular-level annotations. It provides excellent cross-references to other databases and supports pathway overrepresentation analysis (ORA). KEGG (Kyoto Encyclopedia of Genes and Genomes) is a comprehensive resource containing pathway maps, ortholog information, and chemical reactions. While KEGG remains popular, its licensing has become more restrictive. Reactome is generally preferred for open academic use.',
      },
      {
        heading: 'Enrichment analysis',
        content: 'Enrichment analysis determines whether a set of genes (e.g., upregulated in an RNA-seq experiment) contains more genes from a particular pathway than expected by chance. The standard method is Fisher\'s exact test or a hypergeometric test, corrected for multiple testing (Benjamini-Hochberg FDR). The result is a list of pathways ranked by significance, with enrichment ratios and adjusted p-values. Synteny performs pathway enrichment against both Reactome and KEGG databases.',
        code: 'Enrichment analysis results example:\n\nPathway                        Genes   Expected   Ratio   p-value    FDR\n──────────────────────────────────────────────────────────────────────\nDNA Replication                  12       2.1      5.7    8e-12    2e-9\nCell Cycle                       18       4.3      4.2    2e-10    3e-8\np53 Signaling                     8       1.2      6.7    5e-8     4e-6\n\nRatio = observed / expected count\nFDR   = false discovery rate (corrected p-value)',
      },
    ],
  },
  interactions: {
    title: 'Protein Interactions',
    description: 'Exploring the network of physical and functional associations between proteins.',
    sections: [
      {
        heading: 'STRING database',
        content: 'STRING (Search Tool for the Retrieval of Interacting Genes/Proteins) is a comprehensive database of known and predicted protein-protein interactions. It covers over 67 million proteins from more than 14,000 organisms. Interactions are derived from four sources: experimental evidence, curated databases, text mining of scientific literature, and computational predictions (gene neighborhood, gene fusions, gene co-occurrence). Each interaction is scored by how well the evidence supports it.',
      },
      {
        heading: 'Interaction networks',
        content: 'An interaction network consists of nodes (proteins) and edges (interactions). Networks can be visualized with different layout algorithms: force-directed (Fruchterman-Reingold), circular, or hierarchical. The network topology reveals hub proteins (highly connected), bottlenecks, and clusters corresponding to functional modules. Synteny uses the STRING API to fetch interaction data and renders interactive networks using a force-directed layout.',
      },
      {
        heading: 'Confidence scores',
        content: 'STRING assigns each interaction a confidence score from 0 to 1,000, with higher values indicating stronger evidence. Scores are divided into three tiers: low confidence (< 150), medium confidence (150–700), and high confidence (> 700). The combined score integrates evidence from all sources using a naive Bayes approach. For most analyses, filtering at medium confidence (≥ 400) provides a good balance of sensitivity and specificity.',
        code: 'STRING confidence tiers:\n\n  > 700  — High confidence (strong experimental + database evidence)\n  400–700 — Medium confidence (good for most analyses)\n  150–400 — Low confidence (primarily text-mining)\n  < 150  — Very low (likely noise)',
      },
    ],
  },
  docking: {
    title: 'Molecular Docking',
    description: 'Predicting how a small molecule binds to a protein — poses, scores, and interaction fingerprints.',
    sections: [
      {
        heading: 'What is docking?',
        content: 'Molecular docking predicts the preferred orientation (pose) of a small molecule (ligand) when bound to a protein (receptor). The two core problems are sampling — exploring the space of possible ligand poses — and scoring — ranking poses to find the one closest to the true binding mode. Docking is widely used in virtual screening, drug repurposing, and lead optimization. It is a computational filter: a good docking score suggests a compound is worth testing experimentally, never proof it binds.',
      },
      {
        heading: 'Scoring functions',
        content: 'Scoring functions estimate the binding free energy of a pose. They combine terms for van der Waals interactions, electrostatics, hydrogen bonds, desolvation, and entropy. Scoring functions fall into three classes: physics-based (force-field energies), empirical (fit to measured binding affinities), and knowledge-based (derived from statistics of known structures). All scoring functions are approximations — absolute energy values should not be compared across different targets, and even state-of-the-art methods rank well but rarely reproduce absolute affinities.',
      },
      {
        heading: 'Interaction fingerprints',
        content: 'An interaction fingerprint summarizes a docked pose as a binary or weighted vector of contacts: hydrogen bonds, hydrophobic contacts, pi-stacking, and salt bridges. Synteny computes these per-pose so you can compare how different ligands engage the same pocket. Residue-level fingerprints (which residues contact the ligand) are especially useful for explaining selectivity and for validating that a pose makes sensible, specific contacts rather than non-specific packing.',
        code: 'Interaction fingerprint categories:\n\n  Hbond       — H-bond donor/acceptor within ~3.5 Å\n  Hydrophobic — non-polar contact within ~4.5 Å\n  Pi-stacking — aromatic ring stacking (parallel/T-shaped)\n  Salt bridge — charged groups within ~4 Å\n\nEach contact is reported with its residue, distance, and confidence\n(high / moderate / low) based on geometric criteria.',
      },
      {
        heading: 'Confidence and interpretation',
        content: 'Synteny labels every predicted contact with a confidence based on geometry: distance thresholds, angle criteria for pi-stacking, and donor-acceptor complementarity for hydrogen bonds. Treat the whole interaction fingerprint as a hypothesis. Docking identifies plausible binding modes, but affinity (how strongly something binds) requires experimental measurement (ITC, SPR) or at minimum a physics-based rescoring with a validated method.',
      },
    ],
  },
  md: {
    title: 'Molecular Dynamics',
    description: 'Simulating how proteins move over time to study stability, flexibility, and dynamics.',
    sections: [
      {
        heading: 'What is a simulation?',
        content: 'Molecular dynamics (MD) simulates the physical motion of atoms over time by integrating Newton\'s equations of motion. Starting from a structure, every atom is assigned initial velocities (from a temperature-dependent distribution), and the forces between atoms are computed from a force field each timestep. Integrating the equations advances the system forward in time. MD reveals dynamics that static structures hide: loop flexibility, domain motions, unfolding pathways, and the stability of a fold under a chosen temperature and solvent.',
      },
      {
        heading: 'Force fields and solvent',
        content: 'A force field defines the potential energy of a system: bond stretching, angle bending, torsions, van der Waals and electrostatic terms. Common protein force fields include AMBER, CHARMM, and GROMACS. Simulations can run in implicit solvent (a continuum model that is fast but approximate) or explicit solvent (water molecules and ions, more realistic but far more expensive). The choice of force field and solvent model strongly affects results — compare simulations only within the same setup.',
        code: 'Potential energy of a force field (simplified):\n\n  E = Σ bonds k_b(r − r₀)² + Σ angles k_θ(θ − θ₀)²\n    + Σ torsions k_φ(1 + cos(nφ − δ))\n    + Σ vdW ε[(r_min/r)¹² − 2(r_min/r)⁶]\n    + Σ Coulomb qᵢqⱼ/(4πε₀ rᵢⱼ)\n\n  k_b, k_θ   — bond and angle force constants\n  ε, r_min  — Lennard-Jones well depth and radius\n  qᵢ, qⱼ    — partial atomic charges',
      },
      {
        heading: 'RMSD and RMSF',
        content: 'RMSD (root-mean-square deviation) measures how far the structure drifts from a reference (usually the starting frame) after superposition — a global measure of stability. A small, stable RMSD plateau indicates the protein maintains its fold. RMSF (root-mean-square fluctuation) measures per-residue flexibility over the trajectory. High RMSF residues are mobile — typically loops and termini; low RMSF regions are rigid (secondary structure cores). These are the two most useful diagnostics for judging simulation quality.',
        code: 'RMSD = sqrt( (1/N) Σᵢ ||rᵢ(t) − rᵢ(ref)||² )\n\n  rᵢ(t)     — position of atom i at time t\n  rᵢ(ref)   — position of atom i in the reference frame\n  N         — number of atoms (usually backbone Cα only)\n\nRMSF per residue i:\n\n  RMSFᵢ = sqrt( (1/T) Σₜ ||rᵢ(t) − ⟨rᵢ⟩||² )\n\n  ⟨rᵢ⟩ — average position of residue i over the trajectory',
      },
      {
        heading: 'Energy, Rg, and SASA',
        content: 'Beyond RMSD/RMSF, three scalar observables summarize a simulation. Potential energy should stabilize over the equilibration phase and fluctuate around a mean. Radius of gyration (Rg) reports overall compactness — large swings suggest unfolding. Solvent-accessible surface area (SASA) tracks exposure of the protein to solvent; a sudden increase can indicate partial unfolding. Synteny reports all of these as per-frame traces you can export, so you can check that the simulation reached a stable plateau before trusting its conclusions.',
      },
      {
        heading: 'Minimize → Equilibrate → Production',
        content: 'A well-run simulation follows a standard protocol. Minimization removes bad atomic contacts (clashes) from the starting structure using energy minimization. Equilibration gradually heats the system to the target temperature while relaxing the solvent around the protein. Production is the main trajectory collection phase at constant temperature. Synteny exposes all three phases with configurable lengths, so a quick minimization and a full production run share the same pipeline.',
      },
    ],
  },
  admet: {
    title: 'ADMET Prediction',
    description: 'Estimating the drug-like properties of a molecule — absorption, distribution, metabolism, excretion, and toxicity.',
    sections: [
      {
        heading: 'What is ADMET?',
        content: 'ADMET describes the five properties that determine whether a molecule can become a drug. Absorption — how a compound enters the bloodstream. Distribution — where it goes in the body. Metabolism — how it is chemically transformed, primarily by liver cytochrome P450 enzymes. Excretion — how it leaves the body (urine, bile). Toxicity — whether it damages cells, organs, or DNA. Predicting these computationally, before synthesis, is a cornerstone of early-stage drug discovery.',
      },
      {
        heading: 'Lipinski\'s Rule of Five',
        content: 'Lipinski\'s Rule of Five is a heuristic for oral bioavailability: a molecule is likely to be orally absorbed if it has molecular weight ≤ 500, logP ≤ 5, at most 5 hydrogen-bond donors, and at most 10 hydrogen-bond acceptors. The "five" refers to these thresholds all being multiples of 5. Compounds violating two or more rules are likely to have poor permeability and absorption. It is a guideline, not a law — many marketed drugs violate one rule.',
        code: 'Lipinski Rule of Five:\n\n  MW            ≤ 500       daltons\n  logP          ≤ 5\n  H-bond donors ≤ 5\n  H-bond accept ≤ 10\n\n  "Veber rules" (add-on):\n  Rotatable bonds ≤ 10\n  PSA            ≤ 140 Å²\n\nPSA — polar surface area, correlates with permeability',
      },
      {
        heading: 'Physicochemical properties',
        content: 'Synteny computes the fundamental descriptors first: molecular weight, logP (lipophilicity, octanol/water partition), TPSA (topological polar surface area), number of rotatable bonds, hydrogen-bond donors/acceptors, formal charge, and SMILES validity. Lipophilicity drives membrane permeability and solubility; PSA drives the same; rotatable bonds drive flexibility and entropic cost of binding. Together they let you spot at a glance whether a molecule is drug-like or a known-problematic "chimeric" compound.',
      },
      {
        heading: 'Functional groups',
        content: 'Reactive or alerting functional groups flag likely toxicity or metabolic liability. Examples include Michael acceptors, alkyl halides, epoxides, and aromatic amines — each associated with known mechanisms of reactivity with biological nucleophiles (e.g., DNA, proteins). Synteny scans the molecule and lists detected functional groups so a chemist can quickly see potential red flags before investing in synthesis.',
      },
      {
        heading: 'Limitations',
        content: 'Rule-based and descriptor-based ADMET prediction is a screening filter, not a laboratory. It says nothing about actual metabolic clearance, transporter efflux, or tissue-specific toxicity. Modern quantitative methods (QSAR, machine learning, PBPK modeling) refine these estimates but still require experimental validation. Use ADMET results to prioritize which compounds to synthesize — never to conclude a compound is safe.',
      },
    ],
  },
  sequencing: {
    title: 'Sequencing',
    description: 'Reading DNA — Sanger and next-generation methods, quality scores, assembly, and variants.',
    sections: [
      {
        heading: 'Sanger sequencing',
        content: 'Sanger sequencing (chain-termination) is the classic first-generation method. Four reactions each contain template, primer, polymerase, and a mix of normal nucleotides plus one fluorescently labeled dideoxy (chain-terminating) nucleotide. Each incorporated ddNTP stops synthesis, producing fragments of every possible length. Separating the fragments by size reconstructs the sequence from the fluorescent labels. Sanger reads are long (600–1000 bp) and accurate (~99.9%), making it the gold standard for confirming variants and finishing small regions.',
      },
      {
        heading: 'Next-generation sequencing',
        content: 'NGS (next-generation sequencing) parallelizes sequencing across millions of fragments. Illumina sequencing-by-synthesis reads clusters of amplified fragments base-by-base, imaging a fluorescent signal at each cycle. The tradeoff: millions of short reads (75–300 bp) at low per-base cost. NGS powers whole-genome, whole-exome, RNA-seq, ChIP-seq, and metagenomics. The short reads must be aligned to a reference or assembled de novo — bioinformatics is as essential as the wet lab step.',
      },
      {
        heading: 'Quality scores',
        content: 'Every sequenced base carries a Phred quality score Q = −10·log₁₀(P_error), where P_error is the probability the base call is wrong. Q30 means a 1-in-1000 error rate (99.9% accuracy); Q20 means 1-in-100 (99%). Scores are stored as ASCII characters in FASTQ files (the "@header\nSEQ\n+\nQUAL" format). Read quality typically degrades toward the 3\' end, which is why pipelines trim low-quality tails before alignment.',
        code: 'FASTQ format — one read:\n\n  @SEQ_ID description\n  GATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT\n  +\n  !\'\'*((((***+))%%%++)(%%%%).1***-+*\'\'))**55CCF>>>>>>CCCCCCC65\n\n  Phred:  Q = -10 * log10(P)\n  Q20 = 99%   accuracy (1 error per 100 bp)\n  Q30 = 99.9% accuracy (1 error per 1000 bp)\n  ASCII = Phred + 33 (Illumina/Sanger encoding)',
      },
      {
        heading: 'Alignment, assembly, and variants',
        content: 'Short reads are placed onto a reference genome by alignment (BWA, Bowtie2), producing SAM/BAM files with mapping quality scores. De novo assembly stitches reads into contigs when no reference exists, using overlap graphs (canu, flye, SPAdes). Variant calling (GATK HaplotypeCaller, freebayes) compares aligned reads to the reference to find SNPs and indels, each assigned a genotype and quality. Filtering against depth, mapping quality, and strand bias separates real variants from sequencing artifacts.',
      },
    ],
  },
  primers: {
    title: 'Primer Design',
    description: 'Designing oligonucleotide primers for PCR amplification.',
    sections: [
      {
        heading: 'PCR basics',
        content: 'The Polymerase Chain Reaction (PCR) amplifies a specific DNA region between two primer binding sites. Each cycle consists of three steps: denaturation (95°C — separate DNA strands), annealing (50–65°C — primers bind), and extension (72°C — DNA polymerase extends). After 30–35 cycles, the target region is amplified by over a billion-fold. Successful PCR depends on well-designed primers that are specific, have appropriate melting temperatures, and do not form secondary structures.',
      },
      {
        heading: 'Primer3',
        content: 'Primer3 is the most widely used primer design software. It picks PCR primers from a template sequence, optimizing for melting temperature, GC content, primer length, and avoiding problematic features like hairpins, self-dimers, and cross-dimers. Synteny uses Primer3 via its backend API to design primers for any input sequence. The tool evaluates hundreds of candidate primer pairs and returns the best ones ranked by a quality score.',
      },
      {
        heading: 'Melting temperature',
        content: 'The melting temperature (Tm) of a primer is the temperature at which half of the primer molecules are annealed to the template. It depends on primer length, GC content, and salt concentration. A common rule of thumb: Tm = 2°C × (A+T) + 4°C × (G+C). For PCR, primers should have Tm values between 55°C and 65°C, and the forward and reverse primers should have Tm values within 2–5°C of each other.',
        code: 'Tm estimation (nearest-neighbor, simplified):\n\n  Tm = ΔH / (ΔS + R × ln(C/4)) − 273.15 + 16.6 × log([Na+])\n\n  ΔH = enthalpy change\n  ΔS = entropy change\n  R  = gas constant (1.987 cal/mol·K)\n  C  = primer concentration\n\nRule of thumb:\n  Tm ≈ 2(A+T) + 4(G+C)',
      },
      {
        heading: 'GC content',
        content: 'GC content — the percentage of guanine and cytosine bases in a primer — affects both melting temperature and secondary structure formation. Ideal primers have 40–60% GC content. Too high GC content (> 65%) increases the risk of non-specific binding and stable secondary structures. Too low GC content (< 35%) results in weak binding and low Tm. Primers with balanced GC content across the 3\' end provide the most reliable amplification.',
      },
    ],
  },
  tools: {
    title: 'Format Converter',
    description: 'Converting between common bioinformatics sequence formats.',
    sections: [
      {
        heading: 'Format conversion',
        content: 'Synteny supports conversion between FASTA, GenBank, EMBL, and plain text formats. FASTA is the simplest format — a header line starting with ">" followed by the sequence. GenBank and EMBL are richer formats that include annotations, features, and references. When converting between formats, only the sequence and basic header information are preserved. Annotations and features are kept when converting between GenBank and EMBL.',
        code: 'FASTA format:\n\n  >seq_id description\n  ATGCGATCGTAGCTAGCTAGCTAGCATCGATCG\n  GCTAGCTAGCATCGATCGATCGATCGATCGTAG\n\nGenBank format:\n\n  LOCUS       NM_001 1234 bp DNA linear\n  DEFINITION  Sample sequence.\n  ORIGIN\n      1 atgcgatcgt agctagctag ctagcatcga tcg\n     61 gctagctagc atcgatcgat cgatcgtagg tagcta\n  //',
      },
      {
        heading: 'Sequence validation',
        content: 'Sequence validation checks that your input contains only valid residues for the specified molecule type. For DNA, valid characters are A, C, G, T, and U (uracil is converted to thymine). For RNA, valid characters are A, C, G, and U. For protein, valid characters are the 20 standard amino acids (plus B, Z, X, and * for selenocysteine/pyrrolysine/stop). The validator also detects common issues like whitespace, line breaks, and numeric characters embedded in the sequence.',
      },
    ],
  },
  glossary: {
    title: 'Glossary',
    description: 'A–Z reference of bioinformatics terms with plain-English definitions.',
    sections: [
      {
        heading: 'A–C',
        content: 'Alignment — The arrangement of sequences to identify regions of similarity.\nAmino acid — One of 20 organic compounds that form proteins.\nBLAST — Basic Local Alignment Search Tool for finding sequence similarity.\nBit score — Normalized, database-size-independent score from a sequence search.\nBootstrap — Resampling method to assess confidence in phylogenetic tree branches.\nCDS — Coding Sequence, the region of a gene that is translated into protein.\nConserved — A residue or region that remains unchanged across evolution.\nContig — A contiguous sequence assembled from overlapping sequencing reads.',
      },
      {
        heading: 'D–H',
        content: 'Domain — A conserved, independently folding functional unit of a protein.\nE-value — Expect value: number of chance matches expected in a database search.\nEnrichment — Statistical overrepresentation of a pathway in a gene set.\nFASTA — Text-based sequence format using a single-line header starting with ">".\nFDR — False Discovery Rate, a correction for multiple hypothesis testing.\nGap — A space inserted in an alignment to compensate for insertions/deletions.\nGC content — Percentage of guanine and cytosine bases in a sequence.\nHMM — Hidden Markov Model, a statistical model used for profile searches.',
      },
      {
        heading: 'I–M',
        content: 'Identity — The percentage of exactly matching residues in an alignment.\nInterPro — Integrated database of protein domains, families, and functional sites.\nKEGG — Kyoto Encyclopedia of Genes and Genomes, a pathway database.\nLocal alignment — Alignment of only the most similar subsequences (Smith-Waterman).\nMelting temperature (Tm) — Temperature at which half of DNA duplex dissociates.\nML — Maximum Likelihood, a phylogenetic method that optimizes tree topology.\nMSA — Multiple Sequence Alignment, alignment of three or more sequences.\nMutation — A change in the nucleotide sequence of a genome.',
      },
      {
        heading: 'N–R',
        content: 'NJ — Neighbor-Joining, a fast distance-based phylogenetic tree-building method.\nORF — Open Reading Frame, a region of DNA potentially coding for a protein.\nOrtholog — Genes in different species that evolved from a common ancestral gene.\nPCR — Polymerase Chain Reaction, a method to amplify specific DNA sequences.\nPDB — Protein Data Bank, the global repository of 3D macromolecular structures.\nPfam — A database of protein domain families with associated HMM profiles.\nPhylogeny — The evolutionary history and relationships among organisms/sequences.\npLDDT — Predicted Local Distance Difference Test, AlphaFold\'s per-residue confidence.',
      },
      {
        heading: 'S–Z',
        content: 'Scoring matrix — A table of scores for aligning each pair of residues.\nSmith-Waterman — An algorithm for local sequence alignment.\nSTRING — Database of known and predicted protein-protein interactions.\nSubstitution — A residue replaced by another during evolution.\nTopology — The branching pattern of a phylogenetic tree (not including branch lengths).\nTwilight zone — Region of sequence similarity (~20–35% identity) where homology is uncertain.\nUPGMA — Unweighted Pair Group Method with Arithmetic Mean, a distance-based clustering method.\nVariant — A specific form of a genetic sequence that differs from the reference.',
      },
    ],
  },
};

export default function TopicPage() {
  const params = useParams();
  const router = useRouter();
  const topic = params.topic as string;
  const data = topics[topic];

  if (!data) {
    return (
      <div className="text-center py-20">
        <h1 className="text-2xl font-bold text-text-primary mb-2">Topic not found</h1>
        <p className="text-text-muted mb-6">No documentation available for &ldquo;{topic}&rdquo;.</p>
        <CriticalButton onClick={() => router.push('/learn')}>
          Back to Documentation
        </CriticalButton>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <BackButton href="/learn" label="Back to Documentation" />
      <PageHeader title={data.title} subtitle={data.description} />

      <div className="space-y-10">
        {data.sections.map((section, i) => (
          <motion.section
            key={i}
            variants={fadeUp}
            initial={{ y: 24 }}
            animate="show"
          >
            <h2 className="text-lg font-semibold text-text-primary mb-3">{section.heading}</h2>
            <p className="text-sm text-text-secondary leading-relaxed whitespace-pre-line">{section.content}</p>
            {section.code && (
              <pre className="mt-4 p-4 rounded-xl bg-surface-1 border border-glass-border overflow-x-auto text-xs font-mono text-text-secondary leading-relaxed">
                <code>{section.code}</code>
              </pre>
            )}
          </motion.section>
        ))}
      </div>
    </div>
  );
}

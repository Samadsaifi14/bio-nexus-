'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { fadeUp } from '@/lib/animations';
import { ArrowLeft } from 'lucide-react';

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
        content: 'Protein structures can be visualized in several representations: cartoon/ribbon (shows secondary structure), surface (shows solvent-accessible surface), sticks (shows atomic bonds), and spheres (space-filling). Web-based viewers like Mol* (MolStar), NGL Viewer, and 3Dmol.js enable interactive visualization directly in the browser. Bio Nexus uses Mol* for structure rendering, supporting PDB and mmCIF files with customizable color schemes and selection highlighting.',
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
        content: 'Enrichment analysis determines whether a set of genes (e.g., upregulated in an RNA-seq experiment) contains more genes from a particular pathway than expected by chance. The standard method is Fisher\'s exact test or a hypergeometric test, corrected for multiple testing (Benjamini-Hochberg FDR). The result is a list of pathways ranked by significance, with enrichment ratios and adjusted p-values. Bio Nexus performs pathway enrichment against both Reactome and KEGG databases.',
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
        content: 'An interaction network consists of nodes (proteins) and edges (interactions). Networks can be visualized with different layout algorithms: force-directed (Fruchterman-Reingold), circular, or hierarchical. The network topology reveals hub proteins (highly connected), bottlenecks, and clusters corresponding to functional modules. Bio Nexus uses the STRING API to fetch interaction data and renders interactive networks using a force-directed layout.',
      },
      {
        heading: 'Confidence scores',
        content: 'STRING assigns each interaction a confidence score from 0 to 1,000, with higher values indicating stronger evidence. Scores are divided into three tiers: low confidence (< 150), medium confidence (150–700), and high confidence (> 700). The combined score integrates evidence from all sources using a naive Bayes approach. For most analyses, filtering at medium confidence (≥ 400) provides a good balance of sensitivity and specificity.',
        code: 'STRING confidence tiers:\n\n  > 700  — High confidence (strong experimental + database evidence)\n  400–700 — Medium confidence (good for most analyses)\n  150–400 — Low confidence (primarily text-mining)\n  < 150  — Very low (likely noise)',
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
        content: 'Primer3 is the most widely used primer design software. It picks PCR primers from a template sequence, optimizing for melting temperature, GC content, primer length, and avoiding problematic features like hairpins, self-dimers, and cross-dimers. Bio Nexus uses Primer3 via its backend API to design primers for any input sequence. The tool evaluates hundreds of candidate primer pairs and returns the best ones ranked by a quality score.',
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
        content: 'Bio Nexus supports conversion between FASTA, GenBank, EMBL, and plain text formats. FASTA is the simplest format — a header line starting with ">" followed by the sequence. GenBank and EMBL are richer formats that include annotations, features, and references. When converting between formats, only the sequence and basic header information are preserved. Annotations and features are kept when converting between GenBank and EMBL.',
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
        <button
          onClick={() => router.push('/learn')}
          className="btn-primary px-5 py-2.5 text-sm"
        >
          Back to Documentation
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <Link
          href="/learn"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary transition mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Documentation
        </Link>

        <h1 className="text-2xl font-bold text-text-primary mb-2">{data.title}</h1>
        <p className="text-text-muted mb-10 text-sm">{data.description}</p>
      </motion.div>

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

"""
Unit tests for BLAST parameter resolution and sequence-aware validation.

Pure logic — no external API calls.
"""

import pytest


class TestValidateFastaNucleotide:
    def test_protein_fasta_still_valid(self):
        from app.services.validators import validate_fasta

        res = validate_fasta(">p53\nMEEPQSDPSVEPPLSQETFSDLWKLLPENN", "blast")
        assert res.valid
        assert len(res.sequences) == 1

    def test_dna_sequence_now_valid(self):
        from app.services.validators import validate_fasta

        res = validate_fasta(">seq\nATGGCGACCGGCGCTCCCGCCGGGATCGCCATG", "blast")
        assert res.valid
        assert len(res.sequences) == 1

    def test_plain_dna_valid(self):
        from app.services.validators import validate_fasta

        res = validate_fasta("ATGGCGACCGGCGCTCCCGCCGGGATCGCCATG", "blast")
        assert res.valid

    def test_rna_sequence_valid(self):
        from app.services.validators import validate_fasta

        res = validate_fasta("AUGGCGACCGGCGCUCCCGCCGGGAUCGCCAUG", "blast")
        assert res.valid

    def test_protein_invalid_chars_rejected(self):
        from app.services.validators import validate_fasta

        # FASTA path keeps every char, so digits are caught (plain path strips them)
        res = validate_fasta(">query\nMEEPQSDPSVEPPLSQET12345", "blast")
        assert not res.valid

    def test_protein_with_ambiguity_codes_accepted(self):
        from app.services.validators import validate_fasta

        res = validate_fasta("MEEPQSDPSVEPPLSQETBZXOUJ", "blast")
        assert res.valid

    def test_short_sequence_rejected(self):
        from app.services.validators import validate_fasta

        res = validate_fasta("ATG", "blast")
        assert not res.valid
        assert "short" in res.error.lower()


class TestResolveBlastParams:
    def test_protein_defaults(self):
        from app.services.blast_config import resolve_blast_params

        program, database, seq_type = resolve_blast_params("TTCCPSIVARSNFNVCRLPG")
        assert program == "blastp"
        assert database == "nr"
        assert seq_type == "protein"

    def test_dna_defaults(self):
        from app.services.blast_config import resolve_blast_params

        program, database, seq_type = resolve_blast_params("ATGGCGACCGGCGCTCCCGCCGGGATCGCCATG")
        assert program == "blastn"
        assert database == "nt"
        assert seq_type == "dna"

    def test_fast_mode_switches_to_swissprot(self):
        from app.services.blast_config import resolve_blast_params

        program, database, seq_type = resolve_blast_params(
            "TTCCPSIVARSNFNVCRLPG", fast_mode=True
        )
        assert database == "swissprot"

    def test_explicit_program_and_db_respected(self):
        from app.services.blast_config import resolve_blast_params

        program, database, seq_type = resolve_blast_params(
            "TTCCPSIVARSNFNVCRLPG",
            program="blastp",
            database="pdbaa",
        )
        assert program == "blastp"
        assert database == "pdbaa"

    def test_dna_blastx_allowed(self):
        from app.services.blast_config import resolve_blast_params

        program, database, seq_type = resolve_blast_params(
            "ATGGCGACCGGCGCTCCCGCCGGGATCGCCATG",
            program="blastx",
            database="nr",
        )
        assert program == "blastx"
        assert database == "nr"

    def test_protein_rejects_nucleotide_program(self):
        from app.services.blast_config import resolve_blast_params

        with pytest.raises(ValueError):
            resolve_blast_params("TTCCPSIVARSNFNVCRLPG", program="blastn")

    def test_incompatible_db_falls_back(self):
        from app.services.blast_config import resolve_blast_params

        # nr is a protein db — sending it with blastn must not error
        program, database, seq_type = resolve_blast_params(
            "ATGGCGACCGGCGCTCCCGCCGGGATCGCCATG",
            program="blastn",
            database="nr",
        )
        assert database == "nt"

    def test_dna_fast_mode_falls_back_to_refseq_rna(self):
        from app.services.blast_config import resolve_blast_params

        program, database, seq_type = resolve_blast_params(
            "ATGGCGACCGGCGCTCCCGCCGGGATCGCCATG",
            database="swissprot",  # protein db with a DNA query
            fast_mode=True,
        )
        assert database == "refseq_rna"

    def test_unsupported_program_rejected(self):
        from app.services.blast_config import resolve_blast_params

        with pytest.raises(ValueError):
            resolve_blast_params("TTCCPSIVARSNFNVCRLPG", program="megablast")

    def test_unknown_sequence_rejected(self):
        from app.services.blast_config import resolve_blast_params

        with pytest.raises(ValueError):
            resolve_blast_params("1234567890")

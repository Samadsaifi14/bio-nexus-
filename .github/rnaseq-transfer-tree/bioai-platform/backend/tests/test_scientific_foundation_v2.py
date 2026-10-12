from app.benchmarking.bbs2 import evaluate_ai_bundle, registry
from app.engines.stats_engine import benjamini_hochberg, bootstrap_ci, linear_regression, roc_auc
from app.services.evidence_policy import EvidenceClass, classify_claim
from app.services.publication_formats import JOURNAL_FORMATS, completeness, normalize_journal, render_markdown


def test_bbs2_registry_covers_all_requested_domains():
    r=registry()
    assert r["suite"]=="BBS-2"
    for domain in ("sequence","annotation","structure","docking","md","ngs","ai"):
        assert r["domains"].get(domain,0)>0
    assert r["semantics"]=="defined != executed != passed"


def test_ai_numeric_and_citation_fidelity_rejects_unsupported_claims():
    result=evaluate_ai_bundle({
      "generated_text":"The result was 42.0 with accession P12345.",
      "evidence_text":"Observed value: 41.0",
      "generated_citations":["PMID:2"],
      "allowed_citations":["PMID:1"],
      "claims":[{"id":"c1","classification":"AI-generated interpretation","evidence_refs":[]}],
    })
    assert result["passed"] is False
    assert "42.0" in result["benchmarks"]["numeric_fidelity"]["unsupported_numeric_claims"]
    assert result["benchmarks"]["citation_fidelity"]["invalid_citations"]==["PMID:2"]


def test_evidence_policy_rejects_new_number_not_in_support():
    context={"blast":{"identity_pct":97.2,"accession":"P12345"}}
    claim=classify_claim(sentence="Identity was 99.9% for P12345.",evidence_sections=["blast"],context=context)
    assert claim["admitted"] is False
    assert claim["evidence_class"]==EvidenceClass.UNSUPPORTED.value


def test_evidence_policy_accepts_recorded_numeric_claim():
    context={"blast":{"identity_pct":97.2,"accession":"P12345"}}
    claim=classify_claim(sentence="Identity was 97.2 for P12345.",evidence_sections=["blast"],context=context)
    assert claim["admitted"] is True
    assert claim["evidence_class"]==EvidenceClass.DETERMINISTIC.value


def test_bootstrap_is_seed_reproducible_and_reports_n():
    a=bootstrap_ci([1,2,3,4,5],n_boot=250,seed=7)
    b=bootstrap_ci([1,2,3,4,5],n_boot=250,seed=7)
    assert a==b
    assert a["n"]==5
    assert a["ci"][0] <= a["estimate"] <= a["ci"][1]


def test_bh_adjustment_stays_in_unit_interval():
    out=benjamini_hochberg([0.01,0.04,0.03,0.9])
    assert out["n"]==4
    assert all(0 <= p <= 1 for p in out["adjusted_p_values"])


def test_roc_auc_perfect_ranking():
    out=roc_auc([0,0,1,1],[0.1,0.2,0.8,0.9])
    assert out["auc"]==1.0


def test_regression_reports_sample_size_and_r2():
    out=linear_regression([1,2,3,4],[2,4,6,8])
    assert out["n"]==4
    assert abs(out["slope"]-2.0)<1e-12
    assert abs(out["r_squared"]-1.0)<1e-12


def test_every_requested_publication_target_is_registered():
    for journal in ("nature","nature_computational_science","nature_methods","bioinformatics","bmc_bioinformatics","nar_web_server","ieee"):
        assert journal in JOURNAL_FORMATS
        assert normalize_journal(journal)==journal


def test_publication_renderer_does_not_invent_missing_discussion():
    paper={"title":"T","abstract":"A","methods":"M","results":["R"],"figures":[],"references":[],"data_availability":"D","code_availability":"C"}
    md=render_markdown(paper,"nature_methods")
    assert "Discussion requires author interpretation" in md
    report=completeness(paper)
    assert report["complete"] is False

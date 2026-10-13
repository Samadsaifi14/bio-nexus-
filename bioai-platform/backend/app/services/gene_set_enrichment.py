"""Explicit-universe gene-set over-representation analysis."""
import hashlib
import json
import math


def _tail(n, k, draws, observed):
    if observed == 0:
        return 1.0
    def choose(a, b):
        return math.lgamma(a+1)-math.lgamma(b+1)-math.lgamma(a-b+1)
    logs = [choose(k, x)+choose(n-k, draws-x)-choose(n, draws)
            for x in range(max(observed, draws-(n-k)), min(k, draws)+1)]
    peak = max(logs)
    return min(1.0, math.exp(peak)*math.fsum(math.exp(x-peak) for x in logs))


def enrich_gene_sets(query, background, gene_sets, *, source, release, organism, identifier_namespace):
    def ids(values):
        if any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError('Identifiers must be nonempty strings')
        return {v.strip() for v in values}
    query, background = ids(query), ids(background)
    if not query or not background or not query <= background:
        raise ValueError('Nonempty query must be a subset of the explicit background')
    if not gene_sets or len(gene_sets)>5000 or len(query)>5000 or len(background)>100000:
        raise ValueError('Limits: 5000 terms, 5000 query and 100000 background identifiers')
    if sum(len(members) for members in gene_sets.values()) > 2000000:
        raise ValueError('Annotation exceeds 2000000 memberships')
    provenance = dict(source=source, release=release, organism=organism, identifier_namespace=identifier_namespace)
    if any(not isinstance(v, str) or not v.strip() for v in provenance.values()):
        raise ValueError('Source, release, organism and identifier namespace are required')
    rows, annotations, tail_work = [], {}, 0
    for term, members in gene_sets.items():
        if not isinstance(term, str) or not term.strip():
            raise ValueError('Nonempty term identifiers required')
        original = ids(members)
        annotations[term] = sorted(original)
        members = original & background
        if not members:
            continue
        hits = query & members
        if hits:
            tail_work += min(len(members), len(query)) - len(hits) + 1
            if tail_work > 2000000:
                raise ValueError('Analysis exceeds exact-tail computation limit; reduce query or terms')
        rows.append(dict(term_id=term, overlap=sorted(hits), overlap_size=len(hits), term_size=len(members),
                         query_size=len(query), background_size=len(background),
                         p_value=_tail(len(background), len(members), len(query), len(hits)),
                         fold_enrichment=len(hits)*len(background)/(len(query)*len(members))))
    rows.sort(key=lambda r:(r['p_value'], r['term_id']))
    adjusted=1.0
    for rank in range(len(rows),0,-1):
        adjusted=min(adjusted, rows[rank-1]['p_value']*len(rows)/rank)
        rows[rank-1]['adjusted_p_value']=adjusted
        rows[rank-1]['significant']=adjusted<=0.05
    def digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(method='one-sided hypergeometric over-representation analysis', correction_method='Benjamini-Hochberg',
                results=rows, tested_terms=len(rows), excluded_empty_terms=len(gene_sets)-len(rows),
                source_provenance=provenance, query_sha256=digest(sorted(query)),
                background_sha256=digest(sorted(background)), annotation_sha256=digest(annotations),
                background_policy='explicit universe; exact identifier matching; query must be a subset',
                annotation_note='Caller-declared database provenance; not independently verified. No ontology propagation.')

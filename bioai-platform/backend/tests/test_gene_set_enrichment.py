import math
import pytest
from app.services.gene_set_enrichment import enrich_gene_sets, _tail


def run(query, background, terms):
    return enrich_gene_sets(query, background, terms, source='fixture', release='v1',
                            organism='human', identifier_namespace='symbol')


def test_hypergeometric_matches_exact_reference():
    for n in range(2,18):
        for k in range(1,n):
            for draws in range(1,n):
                x=min(k,draws)
                expected=math.comb(k,x)*math.comb(n-k,draws-x)/math.comb(n,draws)
                assert _tail(n,k,draws,x)==pytest.approx(expected, abs=1e-12)


def test_bh_includes_zero_overlap_and_deduplicates():
    result=run(['a','a'], ['a','b','c','d'], {'A':['a','a'],'B':['b'],'empty':['z']})
    assert result['tested_terms']==2
    assert result['excluded_empty_terms']==1
    a,b=result['results']
    assert a['p_value']==pytest.approx(.25)
    assert a['adjusted_p_value']==pytest.approx(.5)
    assert a['fold_enrichment']==4
    assert b['p_value']==1


def test_invalid_universe_rejected():
    with pytest.raises(ValueError,match='subset'):
        run(['z'], ['a'], {'A':['a']})


def test_order_invariance():
    assert run(['a','b'],['a','b','c'],{'T':['b','a']})==run(['b','a'],['c','b','a'],{'T':['a','b']})


def test_zero_overlap_retained():
    row=run(['a'],['a','b'],{'T':['b']})['results'][0]
    assert row['adjusted_p_value']==1
    assert row['overlap']==[]


def test_multi_term_tail_matches_exact_reference():
    for observed in range(1,5):
        expected=sum(math.comb(7,x)*math.comb(13,6-x) for x in range(observed,7))/math.comb(20,6)
        assert _tail(20,7,6,observed)==pytest.approx(expected)


def test_endpoint_contract_and_invalid_background():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.pathways import router
    app=FastAPI()
    app.include_router(router, prefix='/pathways')
    client=TestClient(app)
    payload=dict(identifiers=['a'],background=['a','b'],gene_sets={'term':['a']},
                 source='fixture',release='v1',organism='human',identifier_namespace='symbol')
    response=client.post('/pathways/enrichment/gene-sets',json=payload)
    assert response.status_code==200
    assert response.json()['results'][0]['p_value']==pytest.approx(.5)
    payload['identifiers']=['z']
    assert client.post('/pathways/enrichment/gene-sets',json=payload).status_code==422

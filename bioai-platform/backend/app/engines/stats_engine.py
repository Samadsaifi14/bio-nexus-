"""Central statistical framework for BioNexus.

All public helpers return sample size and method metadata.  Methods that require
an unavailable exact distribution do not fabricate p-values; they report the
computed statistic and an explicit limitation instead.
"""
from __future__ import annotations

import math
import random
from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport
from app.figure.engine import bar_chart_panel


def _mean(v): return sum(v) / len(v) if v else 0.0

def _var(v):
    if len(v) < 2: return 0.0
    m = _mean(v)
    return sum((x-m)**2 for x in v)/(len(v)-1)

def _p_from_z(z): return math.erfc(abs(z)/math.sqrt(2))

def percentile(values, q):
    if not values: return None
    x=sorted(values); p=(len(x)-1)*q; lo=int(math.floor(p)); hi=int(math.ceil(p))
    return x[lo] if lo==hi else x[lo]+(x[hi]-x[lo])*(p-lo)


def bootstrap_ci(values:list[float], confidence:float=.95, n_boot:int=2000, seed:int=0)->dict:
    vals=[float(x) for x in values]
    if not vals: return {"method":"bootstrap_mean_ci","n":0,"estimate":None,"ci":None,"confidence":confidence}
    rng=random.Random(seed); n=len(vals); samples=[]
    for _ in range(max(100,int(n_boot))): samples.append(_mean([vals[rng.randrange(n)] for _ in range(n)]))
    a=(1-confidence)/2
    return {"method":"percentile_bootstrap","n":n,"estimate":_mean(vals),"ci":[percentile(samples,a),percentile(samples,1-a)],"confidence":confidence,"iterations":max(100,int(n_boot)),"seed":seed}


def cohens_d(a,b):
    if len(a)<2 or len(b)<2:return 0.0
    pooled=math.sqrt(((len(a)-1)*_var(a)+(len(b)-1)*_var(b))/(len(a)+len(b)-2))
    return 0.0 if pooled==0 else (_mean(a)-_mean(b))/pooled


def welch_t(a:list[float],b:list[float],alpha:float=.05)->dict:
    a=[float(x) for x in a]; b=[float(x) for x in b]; na,nb=len(a),len(b)
    if na<2 or nb<2:return {"method":"welch_t","n":na+nb,"n_a":na,"n_b":nb,"statistic":None,"p_value":None,"alpha":alpha,"significant":False,"limitation":"at least two observations per group required"}
    va,vb=_var(a),_var(b); se2=va/na+vb/nb
    if se2<=0:return {"method":"welch_t","n":na+nb,"n_a":na,"n_b":nb,"statistic":0.0,"p_value":1.0,"alpha":alpha,"significant":False,"effect_size":0.0}
    t=(_mean(a)-_mean(b))/math.sqrt(se2); p=min(max(_p_from_z(t),0),1)
    return {"method":"welch_t_normal_approximation","n":na+nb,"n_a":na,"n_b":nb,"statistic":t,"p_value":p,"alpha":alpha,"significant":p<=alpha,"effect_size":cohens_d(a,b),"mean_a":_mean(a),"mean_b":_mean(b),"limitation":"p-value uses normal approximation; exact t CDF is not claimed"}


def _rankdata(values):
    order=sorted(values); out=[]
    for v in values:
        lo=order.index(v)+1; hi=len(order)-order[::-1].index(v); out.append((lo+hi)/2)
    return out


def mann_whitney_u(a,b,alpha=.05):
    a=[float(x) for x in a]; b=[float(x) for x in b]; na,nb=len(a),len(b)
    if not a or not b:return {"method":"mann_whitney_u","n":na+nb,"statistic":None,"p_value":None,"alpha":alpha,"significant":False}
    ranks=_rankdata(a+b); u1=na*nb+na*(na+1)/2-sum(ranks[:na]); u2=na*nb-u1
    mu=na*nb/2; sigma=math.sqrt(na*nb*(na+nb+1)/12) or 1; z=(max(u1,u2)-.5-mu)/sigma; p=min(max(_p_from_z(z),0),1)
    return {"method":"mann_whitney_u_normal_approximation","n":na+nb,"n_a":na,"n_b":nb,"statistic":min(u1,u2),"p_value":p,"alpha":alpha,"significant":p<=alpha,"effect_size":cohens_d(a,b)}


def permutation_test(a,b,iterations=5000,seed=0,alpha=.05):
    a=[float(x) for x in a]; b=[float(x) for x in b]; obs=abs(_mean(a)-_mean(b)); pool=a+b; n=len(a)
    if not a or not b:return {"method":"permutation_mean_difference","n":len(pool),"p_value":None,"statistic":None}
    rng=random.Random(seed); extreme=0; it=max(100,int(iterations))
    for _ in range(it):
        x=pool[:]; rng.shuffle(x)
        if abs(_mean(x[:n])-_mean(x[n:]))>=obs-1e-15: extreme+=1
    p=(extreme+1)/(it+1)
    return {"method":"permutation_mean_difference","n":len(pool),"n_a":len(a),"n_b":len(b),"statistic":obs,"p_value":p,"alpha":alpha,"significant":p<=alpha,"iterations":it,"seed":seed}


def benjamini_hochberg(p_values:list[float])->dict:
    m=len(p_values); order=sorted(range(m),key=lambda i:p_values[i]); adj=[1.0]*m; running=1.0
    for rank_pos in range(m-1,-1,-1):
        i=order[rank_pos]; rank=rank_pos+1; running=min(running,float(p_values[i])*m/rank); adj[i]=min(1.0,running)
    return {"method":"Benjamini-Hochberg FDR","n":m,"adjusted_p_values":adj}


def roc_auc(labels:list[int],scores:list[float])->dict:
    pairs=sorted(zip(scores,labels),reverse=True); pos=sum(1 for _,y in pairs if y==1); neg=len(pairs)-pos
    if pos==0 or neg==0:return {"method":"ROC/AUC","n":len(pairs),"auc":None,"curve":[],"limitation":"both classes required"}
    tp=fp=0; curve=[{"fpr":0.0,"tpr":0.0,"threshold":None}]
    last=None
    for s,y in pairs:
        if last is not None and s!=last: curve.append({"fpr":fp/neg,"tpr":tp/pos,"threshold":last})
        if y==1:tp+=1
        else:fp+=1
        last=s
    curve.append({"fpr":1.0,"tpr":1.0,"threshold":last}); auc=0.0
    for p,q in zip(curve,curve[1:]): auc+=(q["fpr"]-p["fpr"])*(p["tpr"]+q["tpr"])/2
    return {"method":"ROC trapezoidal AUC","n":len(pairs),"positives":pos,"negatives":neg,"auc":auc,"curve":curve}


def precision_recall(labels:list[int],scores:list[float])->dict:
    pairs=sorted(zip(scores,labels),reverse=True); positives=sum(labels)
    if positives==0:return {"method":"precision-recall","n":len(labels),"average_precision":None,"curve":[]}
    tp=fp=0; curve=[]; ap=0.0; prev_recall=0.0
    for s,y in pairs:
        if y==1:tp+=1
        else:fp+=1
        precision=tp/(tp+fp); recall=tp/positives; ap+=precision*(recall-prev_recall); prev_recall=recall
        curve.append({"threshold":s,"precision":precision,"recall":recall})
    return {"method":"precision-recall average precision","n":len(labels),"average_precision":ap,"curve":curve}


def calibration(labels:list[int],probs:list[float],bins:int=10)->dict:
    bins=max(2,min(50,int(bins))); groups=[[] for _ in range(bins)]
    for y,p in zip(labels,probs): groups[min(bins-1,max(0,int(float(p)*bins)))].append((int(y),float(p)))
    rows=[]; brier=_mean([(float(p)-int(y))**2 for y,p in zip(labels,probs)]) if labels else None
    for i,g in enumerate(groups):
        if g: rows.append({"bin":i,"n":len(g),"mean_predicted":_mean([p for y,p in g]),"observed_frequency":_mean([y for y,p in g])})
    return {"method":"reliability_diagram","n":len(labels),"bins":rows,"brier_score":brier}


def one_way_anova(groups:list[list[float]])->dict:
    gs=[[float(x) for x in g] for g in groups if g]; n=sum(map(len,gs)); k=len(gs)
    if k<2 or n<=k:return {"method":"one_way_anova","n":n,"groups":k,"f_statistic":None,"p_value":None,"limitation":"at least two groups and residual degrees of freedom required"}
    grand=_mean([x for g in gs for x in g]); ssb=sum(len(g)*(_mean(g)-grand)**2 for g in gs); ssw=sum(sum((x-_mean(g))**2 for x in g) for g in gs); dfb=k-1; dfw=n-k
    f=(ssb/dfb)/(ssw/dfw) if ssw>0 else math.inf; eta=ssb/(ssb+ssw) if ssb+ssw else 0.0
    return {"method":"one_way_anova","n":n,"groups":k,"f_statistic":f,"df_between":dfb,"df_within":dfw,"effect_size_eta_squared":eta,"p_value":None,"limitation":"exact F-distribution p-value intentionally omitted without a validated CDF implementation"}


def linear_regression(x:list[float],y:list[float])->dict:
    n=min(len(x),len(y)); x=[float(v) for v in x[:n]]; y=[float(v) for v in y[:n]]
    if n<2:return {"method":"ordinary_least_squares","n":n,"slope":None,"intercept":None,"r_squared":None}
    mx,my=_mean(x),_mean(y); sxx=sum((v-mx)**2 for v in x)
    slope=sum((a-mx)*(b-my) for a,b in zip(x,y))/sxx if sxx else 0.0; intercept=my-slope*mx; pred=[intercept+slope*v for v in x]; sst=sum((v-my)**2 for v in y); sse=sum((a-b)**2 for a,b in zip(y,pred)); r2=1-sse/sst if sst else 1.0
    return {"method":"ordinary_least_squares","n":n,"slope":slope,"intercept":intercept,"r_squared":r2,"rmse":math.sqrt(sse/n)}


def power_two_sample(effect_size:float,alpha=.05,power=.8)->dict:
    # Normal-approximation planning equation, explicit approximation.
    def inv_norm(p):
        # Acklam-style bisection over erf CDF; deterministic and sufficient for planning.
        lo,hi=-8.0,8.0
        for _ in range(80):
            mid=(lo+hi)/2; c=.5*(1+math.erf(mid/math.sqrt(2)))
            if c<p:lo=mid
            else:hi=mid
        return (lo+hi)/2
    d=abs(float(effect_size))
    if d==0:return {"method":"two_sample_normal_approx_power","effect_size":d,"required_n_per_group":None,"limitation":"effect size must be non-zero"}
    za=inv_norm(1-alpha/2); zb=inv_norm(power); n=math.ceil(2*((za+zb)/d)**2)
    return {"method":"two_sample_normal_approx_power","effect_size":d,"alpha":alpha,"target_power":power,"required_n_per_group":n,"limitation":"planning approximation, not an exact noncentral-t calculation"}


def distribution_diagnostics(values:list[float])->dict:
    v=[float(x) for x in values]; n=len(v)
    if n<2:return {"method":"distribution_diagnostics","n":n}
    m=_mean(v); sd=math.sqrt(_var(v)); skew=_mean([((x-m)/sd)**3 for x in v]) if sd else 0; kurt=_mean([((x-m)/sd)**4 for x in v])-3 if sd else 0; q1=percentile(v,.25); q3=percentile(v,.75); iqr=q3-q1; out=[x for x in v if x<q1-1.5*iqr or x>q3+1.5*iqr]
    return {"method":"distribution_diagnostics","n":n,"mean":m,"sd":sd,"median":percentile(v,.5),"q1":q1,"q3":q3,"skewness":skew,"excess_kurtosis":kurt,"iqr_outlier_count":len(out)}


def kaplan_meier(times:list[float],events:list[int])->dict:
    rows=sorted((float(t),int(e)) for t,e in zip(times,events)); at_risk=len(rows); survival=1.0; curve=[{"time":0.0,"survival":1.0,"at_risk":at_risk}]
    for t in sorted(set(t for t,e in rows)):
        ds=sum(1 for tt,e in rows if tt==t and e==1); cens=sum(1 for tt,e in rows if tt==t and e==0)
        if at_risk and ds: survival*=1-ds/at_risk
        curve.append({"time":t,"survival":survival,"at_risk":at_risk,"events":ds,"censored":cens}); at_risk-=ds+cens
    return {"method":"Kaplan-Meier","n":len(rows),"events":sum(events[:len(rows)]),"curve":curve}


def run_framework(spec:dict)->dict:
    op=str(spec.get("operation") or "").lower(); alpha=float(spec.get("alpha",.05))
    mapping={
      "bootstrap":lambda:bootstrap_ci(spec.get("values") or [],float(spec.get("confidence",.95)),int(spec.get("iterations",2000)),int(spec.get("seed",0))),
      "welch_t":lambda:welch_t(spec.get("group_a") or [],spec.get("group_b") or [],alpha),
      "mann_whitney":lambda:mann_whitney_u(spec.get("group_a") or [],spec.get("group_b") or [],alpha),
      "permutation":lambda:permutation_test(spec.get("group_a") or [],spec.get("group_b") or [],int(spec.get("iterations",5000)),int(spec.get("seed",0)),alpha),
      "multiple_testing":lambda:benjamini_hochberg(spec.get("p_values") or []),
      "roc":lambda:roc_auc(spec.get("labels") or [],spec.get("scores") or []),
      "pr":lambda:precision_recall(spec.get("labels") or [],spec.get("scores") or []),
      "calibration":lambda:calibration(spec.get("labels") or [],spec.get("scores") or [],int(spec.get("bins",10))),
      "anova":lambda:one_way_anova(spec.get("groups") or []),
      "regression":lambda:linear_regression(spec.get("x") or [],spec.get("y") or []),
      "power":lambda:power_two_sample(float(spec.get("effect_size",0)),alpha,float(spec.get("power",.8))),
      "diagnostics":lambda:distribution_diagnostics(spec.get("values") or []),
      "survival":lambda:kaplan_meier(spec.get("times") or [],spec.get("events") or []),
    }
    if op not in mapping:return {"operation":op,"error":"unsupported statistical operation"}
    result=mapping[op](); result.setdefault("alpha",alpha if op not in {"bootstrap","roc","pr","calibration","regression","diagnostics","survival"} else None); return result


def z_score_anomalies(values,threshold=3.0):
    if len(values)<3:return []
    m=_mean(values); sd=math.sqrt(_var(values)) or 1
    return [{"index":i,"value":v,"z_score":(v-m)/sd,"flagged":abs((v-m)/sd)>threshold} for i,v in enumerate(values)]


class StatsEngine(BaseEngine):
    name="stats"; version="2.0.0"; tool="BioNexus central statistical framework"; tool_version="2.0.0"; databases=["recorded experiment data"]
    parameters={"operations":["bootstrap","welch_t","mann_whitney","permutation","multiple_testing","roc","pr","calibration","anova","regression","power","diagnostics","survival"],"reporting":"sample size + method + CI/significance metadata where applicable"}
    citations=["Welch BL. Biometrika 34:28-35, 1947.","Benjamini Y, Hochberg Y. JRSS B 57:289-300, 1995.","Kaplan EL, Meier P. JASA 53:457-481, 1958."]
    benchmarks=["STATS_P_VALUE_IN_UNIT_INTERVAL","BBS-2 statistical regression suite"]; export_formats=["json","csv"]

    def parse(self,raw:Any)->EngineResult:
        raw=raw if isinstance(raw,dict) else {}; alpha=float(raw.get("alpha",.05)); tests=[]
        for spec in raw.get("tests") or []:
            typ=(spec.get("type") or "").lower(); ga=spec.get("group_a") or []; gb=spec.get("group_b") or []
            if typ in {"welch","welch_t"}: tests.append({"name":spec.get("name","test"),**welch_t(ga,gb,alpha)})
            elif typ in {"mann_whitney_u","mann_whitney","mann-whitney"}: tests.append({"name":spec.get("name","test"),**mann_whitney_u(ga,gb,alpha)})
        analyses=[run_framework(s) for s in (raw.get("analyses") or []) if isinstance(s,dict)]
        anomalies=z_score_anomalies([float(x) for x in raw.get("values",[]) if isinstance(x,(int,float))],float(raw.get("anomaly_threshold",3)))
        return EngineResult(engine=self.name,tool=self.tool,database=self.databases[0],input_ref=f"{len(tests)} tests, {len(analyses)} framework analyses",statistics={"tests_run":len(tests),"analyses_run":len(analyses),"significant":sum(1 for t in tests if t.get("significant")),"alpha":alpha,"anomalies_flagged":sum(1 for a in anomalies if a["flagged"])},evidence={"tests":tests,"analyses":analyses,"anomalies":anomalies,"alpha":alpha})

    def validate(self,result:EngineResult)->ValidationReport:
        checks=super().validate(result).checks; tests=result.evidence.get("tests") or []; analyses=result.evidence.get("analyses") or []; alpha=result.statistics.get("alpha")
        pvals=[t.get("p_value") for t in tests if t.get("p_value") is not None]
        checks += [{"name":"alpha_bounded","passed":0<alpha<1,"detail":f"alpha={alpha}"},{"name":"p_values_in_unit_interval","passed":all(0<=p<=1 for p in pvals),"detail":f"{len(pvals)} p-values checked"},{"name":"framework_no_unknown_errors","passed":all("error" not in a for a in analyses),"detail":f"{len(analyses)} analyses"}]
        return ValidationReport(checks,self.name)

    def _export_csv(self,result:EngineResult)->str:
        rows=["name,method,n,statistic,p_value,effect_size"]
        for t in result.evidence.get("tests") or []: rows.append(f"{t.get('name','')},{t.get('method','')},{t.get('n','')},{t.get('statistic','')},{t.get('p_value','')},{t.get('effect_size','')}")
        return "\n".join(rows)

    def figure(self,result:EngineResult)->str:
        tests=result.evidence.get("tests") or []; rows=[(t.get("name",f"test{i}")[:16],-10*math.log10(max(float(t.get("p_value") or 1),1e-10))) for i,t in enumerate(tests)]
        body=bar_chart_panel(rows,x=30,y=70,w=480,h=260,value_label="-log10 p")
        return '<svg xmlns="http://www.w3.org/2000/svg" width="540" height="400" viewBox="0 0 540 400"><rect width="540" height="400" fill="#fff"/><text x="30" y="32" font-size="14" font-weight="bold">Statistical significance</text>'+body+f'<text x="30" y="382" font-size="9">BioNexus Stats Engine v{self.version}</text></svg>'


stats_engine=StatsEngine()

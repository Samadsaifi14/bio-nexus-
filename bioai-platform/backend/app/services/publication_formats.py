"""Journal-specific publication formatting for BioNexus manuscript artifacts.

Formatting changes structure and presentation only. It never invents missing
scientific content; sections absent from the recorded paper are labelled as not
available from the experiment rather than synthesized speculatively.
"""
from __future__ import annotations

import re
from typing import Any

JOURNAL_FORMATS: dict[str, dict[str, Any]] = {
    "nature": {"label":"Nature","abstract_label":"Abstract","methods_label":"Methods","results_label":"Results","discussion":True,"numbered_refs":True},
    "nature_computational_science": {"label":"Nature Computational Science","abstract_label":"Abstract","methods_label":"Methods","results_label":"Results","discussion":True,"numbered_refs":True},
    "nature_methods": {"label":"Nature Methods","abstract_label":"Abstract","methods_label":"Methods","results_label":"Results","discussion":True,"numbered_refs":True},
    "bioinformatics": {"label":"Bioinformatics","abstract_label":"Abstract","methods_label":"Materials and methods","results_label":"Results","discussion":True,"numbered_refs":False},
    "bmc_bioinformatics": {"label":"BMC Bioinformatics","abstract_label":"Abstract","methods_label":"Methods","results_label":"Results","discussion":True,"numbered_refs":False},
    "nar_web_server": {"label":"Nucleic Acids Research Web Server","abstract_label":"Abstract","methods_label":"Materials and Methods","results_label":"Web server / Results","discussion":True,"numbered_refs":True},
    "ieee": {"label":"IEEE","abstract_label":"Abstract","methods_label":"II. METHODS","results_label":"III. RESULTS","discussion":False,"numbered_refs":True},
}

ALIASES = {"bmc":"bmc_bioinformatics","nar":"nar_web_server","nature_cs":"nature_computational_science","ncs":"nature_computational_science","nmeth":"nature_methods"}


def normalize_journal(journal:str)->str:
    key=(journal or "bmc_bioinformatics").strip().lower().replace("-","_").replace(" ","_")
    key=ALIASES.get(key,key)
    if key not in JOURNAL_FORMATS: raise ValueError(f"unsupported journal format: {journal}")
    return key


def _value(paper:dict,key:str,default:str="Not available from the recorded experiment.")->str:
    value=paper.get(key)
    if value is None or value=="" or value==[]: return default
    if isinstance(value,list): return "\n".join(str(x) for x in value)
    return str(value)


def completeness(paper:dict)->dict:
    required=["title","abstract","methods","results","figures","data_availability","code_availability","references"]
    missing=[k for k in required if not paper.get(k)]
    return {"required_sections":required,"missing_sections":missing,"complete":not missing,"result_statement_count":len(paper.get("results") or []),"figure_count":len(paper.get("figures") or []),"reference_count":len(paper.get("references") or [])}


def render_markdown(paper:dict,journal:str)->str:
    key=normalize_journal(journal); spec=JOURNAL_FORMATS[key]
    lines=[f"# {_value(paper,'title')}",f"\n**Target format:** {spec['label']}",f"\n## {spec['abstract_label']}",_value(paper,"abstract")]
    if key=="bmc_bioinformatics": lines += ["\n## Background",_value(paper,"background","Background was not separately generated from this experiment.")]
    else: lines += ["\n## Introduction",_value(paper,"introduction","Introduction requires author-provided scientific context and was not fabricated from the run.")]
    lines += [f"\n## {spec['methods_label']}",_value(paper,"methods"),f"\n## {spec['results_label']}"]
    for row in paper.get("results") or []: lines.append(str(row))
    if spec.get("discussion"): lines += ["\n## Discussion",_value(paper,"discussion","Discussion requires author interpretation; BioNexus did not generate unsupported discussion text.")]
    lines += ["\n## Figure legends"]
    for fig in paper.get("figures") or []: lines.append(f"**{fig.get('figure','Figure')}.** {fig.get('caption','')} Source: {fig.get('source','recorded experiment')}")
    lines += ["\n## Tables"]
    tables=paper.get("tables") or []
    lines += [str(t) for t in tables] if tables else ["No standalone publication tables were generated from this experiment."]
    lines += ["\n## Supplementary data"]
    for item in paper.get("supplementary") or []: lines.append(f"- {item.get('name')}: {item.get('format')} ({item.get('source','recorded result')})")
    lines += ["\n## Statistical appendix",str(paper.get("statistics") or "No statistical summary recorded."),"\n## Data availability",_value(paper,"data_availability"),"\n## Code availability",_value(paper,"code_availability"),"\n## References"]
    for i,ref in enumerate(paper.get("references") or [],1): lines.append(f"{i}. {ref}" if spec.get("numbered_refs") else f"- {ref}")
    check=completeness(paper); lines += ["\n## Reproducibility status",f"Publication completeness check: {'PASS' if check['complete'] else 'INCOMPLETE'}; missing sections: {', '.join(check['missing_sections']) or 'none'}." ]
    return "\n".join(lines).strip()+"\n"


def _latex_escape(text:str)->str:
    repl={"\\":"\\textbackslash{}","&":"\\&","%":"\\%","$":"\\$","#":"\\#","_":"\\_","{":"\\{","}":"\\}","~":"\\textasciitilde{}","^":"\\textasciicircum{}"}
    return "".join(repl.get(c,c) for c in str(text))


def render_latex(paper:dict,journal:str)->str:
    key=normalize_journal(journal); spec=JOURNAL_FORMATS[key]
    parts=["\\documentclass{article}","\\usepackage[margin=1in]{geometry}","\\begin{document}",f"\\title{{{_latex_escape(_value(paper,'title'))}}}","\\maketitle",f"\\section*{{{_latex_escape(spec['abstract_label'])}}}",_latex_escape(_value(paper,"abstract")),f"\\section*{{{_latex_escape(spec['methods_label'])}}}",_latex_escape(_value(paper,"methods")),f"\\section*{{{_latex_escape(spec['results_label'])}}}"]
    parts += [_latex_escape(x)+"\\par" for x in paper.get("results") or []]
    parts += ["\\section*{Figure legends}"]
    parts += [_latex_escape(f"{f.get('figure','Figure')}: {f.get('caption','')}")+"\\par" for f in paper.get("figures") or []]
    parts += ["\\section*{Data availability}",_latex_escape(_value(paper,"data_availability")),"\\section*{Code availability}",_latex_escape(_value(paper,"code_availability")),"\\section*{References}"]
    parts += [_latex_escape(f"{i}. {r}")+"\\par" for i,r in enumerate(paper.get("references") or [],1)]
    parts += ["\\end{document}"]
    return "\n".join(parts)+"\n"

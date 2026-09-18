"use client";

import type { PipelineDomainEvidence } from "@/types/pipeline";
import { downloadTsv } from "@/lib/export-utils";

export function BlastDomainEvidence({ data }: { data: PipelineDomainEvidence }) {
  const domains = Array.isArray(data.domains) ? data.domains : [];
  const seqLen = data.sequence_length || Math.max(0, ...domains.map((d) => Number(d.end || 0)));

  if (data.error && domains.length === 0) {
    return (
      <div className="data-card p-5 border border-warn/20">
        <h3 className="text-sm font-semibold text-text-primary">Domain evidence</h3>
        <p className="mt-1 text-xs text-warn">{data.error}</p>
      </div>
    );
  }

  return (
    <div className="data-card p-5 space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Domain evidence</h3>
          <p className="text-xs text-text-muted mt-1">
            {domains.length} domain annotation{domains.length === 1 ? "" : "s"}
            {data.uniprot_accession ? ` · ${data.uniprot_accession}` : " · sequence-based InterPro evidence"}
            {seqLen ? ` · ${seqLen} aa` : ""}
          </p>
        </div>
        {domains.length > 0 && (
          <button
            onClick={() =>
              downloadTsv(
                ["Accession", "Name", "Source", "Start", "End", "Score"],
                domains.map((d) => [
                  d.accession || "",
                  d.name || d.description || "",
                  d.source_db || "",
                  d.start != null ? String(d.start) : "",
                  d.end != null ? String(d.end) : "",
                  d.score != null ? String(d.score) : "",
                ]),
                `blast-domains-${data.uniprot_accession || "sequence"}.tsv`,
              )
            }
            className="btn-ghost text-xs px-2 py-1"
          >
            Export TSV
          </button>
        )}
      </div>

      {domains.length === 0 ? (
        <p className="text-sm text-text-muted">No domain annotations were returned by the recorded domain-analysis step.</p>
      ) : (
        <>
          {seqLen > 0 && (
            <div className="relative h-14 rounded-xl border border-glass-border bg-surface-1 px-3 pt-6 overflow-hidden">
              <div className="absolute left-3 right-3 top-8 h-1 rounded-full bg-glass-border" />
              {domains.slice(0, 40).map((domain, index) => {
                const start = Math.max(1, Number(domain.start || 1));
                const end = Math.max(start, Number(domain.end || start));
                const left = ((start - 1) / seqLen) * 100;
                const width = Math.max(0.8, ((end - start + 1) / seqLen) * 100);
                return (
                  <div
                    key={`${domain.accession || domain.name || "domain"}-${index}`}
                    className="absolute top-6 h-5 rounded border border-accent-cyan/40 bg-accent-cyan/20"
                    style={{
                      left: `calc(12px + (100% - 24px) * ${left / 100})`,
                      width: `calc((100% - 24px) * ${width / 100})`,
                    }}
                    title={`${domain.accession || ""} ${domain.name || domain.description || ""} ${start}–${end}`.trim()}
                  />
                );
              })}
              <span className="absolute left-3 bottom-1 text-[9px] font-mono text-text-muted">1</span>
              <span className="absolute right-3 bottom-1 text-[9px] font-mono text-text-muted">{seqLen}</span>
            </div>
          )}

          <div className="overflow-x-auto rounded-xl border border-glass-border">
            <table className="w-full text-xs">
              <thead className="bg-surface-1">
                <tr>
                  {["Accession", "Domain", "Source", "Range", "Score"].map((header) => (
                    <th key={header} className="px-3 py-2 text-left text-text-muted font-medium">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {domains.slice(0, 30).map((domain, index) => (
                  <tr key={`${domain.accession || domain.name || "domain"}-${index}`} className="border-t border-glass-border">
                    <td className="px-3 py-2 font-mono text-accent-cyan">{domain.accession || "—"}</td>
                    <td className="px-3 py-2 text-text-primary">{domain.name || domain.description || "Domain"}</td>
                    <td className="px-3 py-2 text-text-muted">{domain.source_db || "InterPro"}</td>
                    <td className="px-3 py-2 font-mono text-text-muted">
                      {domain.start != null && domain.end != null ? `${domain.start}–${domain.end}` : "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-text-muted">
                      {domain.score != null ? Number(domain.score).toPrecision(3) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {domains.length > 30 && (
            <p className="text-[11px] text-text-muted">Showing the first 30 of {domains.length} recorded annotations.</p>
          )}
        </>
      )}
    </div>
  );
}

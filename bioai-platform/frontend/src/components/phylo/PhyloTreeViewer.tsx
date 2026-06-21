"use client";
import { useEffect, useState, useRef } from "react";
import { exportSvgPng } from "@/lib/export-utils";

type TreeNode = { name: string; length: number; children: TreeNode[] };

function parseNewick(s: string): TreeNode {
  const stack: TreeNode[] = [];
  let node: TreeNode = { name: "", length: 1, children: [] };
  let i = 0;

  while (i < s.length) {
    const ch = s[i];
    if (ch === "(") {
      const child: TreeNode = { name: "", length: 1, children: [] };
      node.children.push(child);
      stack.push(node);
      node = child;
    } else if (ch === ",") {
      const sibling: TreeNode = { name: "", length: 1, children: [] };
      stack[stack.length - 1].children.push(sibling);
      node = sibling;
    } else if (ch === ")") {
      node = stack.pop()!;
    } else if (ch === ":") {
      i++;
      let numStr = "";
      while (i < s.length && /[0-9.eE+\-]/.test(s[i])) { numStr += s[i]; i++; }
      node.length = parseFloat(numStr) || 0.1;
      continue;
    } else if (ch !== ";") {
      let name = "";
      while (i < s.length && !["(", ")", ",", ":", ";"].includes(s[i])) { name += s[i]; i++; }
      node.name = name.trim();
      continue;
    }
    i++;
  }
  return node;
}

type LayoutNode = { name: string; length: number; children: LayoutNode[]; x: number; y: number; depth: number };

function layout(root: TreeNode, width: number, height: number): LayoutNode[] {
  const leaves: TreeNode[] = [];
  const collect = (n: TreeNode) => {
    if (!n.children.length) leaves.push(n);
    else n.children.forEach(collect);
  };
  collect(root);

  const nodeMap = new Map<TreeNode, LayoutNode>();
  const leafSpacing = height / (leaves.length + 1);

  let leafIdx = 0;
  const assignY = (n: TreeNode, depth: number): LayoutNode => {
    const ln: LayoutNode = { name: n.name, length: n.length, children: [], x: 0, y: 0, depth };
    nodeMap.set(n, ln);
    if (!n.children.length) {
      ln.y = (++leafIdx) * leafSpacing;
    } else {
      const kids = n.children.map(c => assignY(c, depth + n.length));
      ln.children = kids;
      ln.y = (kids[0].y + kids[kids.length - 1].y) / 2;
    }
    return ln;
  };

  const laid = assignY(root, 0);
  const maxDepth = Math.max(...Array.from(nodeMap.values()).map(n => n.depth));
  const scaleX = (d: number) => 40 + (d / maxDepth) * (width - 160);

  const nodes: LayoutNode[] = [];
  const setX = (n: LayoutNode) => {
    n.x = scaleX(n.depth);
    nodes.push(n);
    n.children.forEach(setX);
  };
  setX(laid);
  return nodes;
}

export function PhyloTreeViewer({ jobId, newick: propNewick }: { jobId?: string; newick?: string }) {
  const [newick, setNewick] = useState<string | null>(propNewick ?? null);
  const [loading, setLoading] = useState(!propNewick);
  const [error, setError] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (propNewick) { setNewick(propNewick); setLoading(false); return; }
    if (!jobId) return;
    fetch(`/api/backend/api/alignment/phylotree?job_id=${jobId}`)
      .then(r => { if (!r.ok) throw new Error("No tree"); return r.text(); })
      .then(setNewick)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [jobId, propNewick]);

  if (loading) return <div className="text-text-muted text-sm animate-pulse">Building phylogenetic tree&hellip;</div>;
  if (error) return <div className="text-error text-sm">{error}</div>;
  if (!newick) return null;

  const W = 600, H = 400;
  const root = parseNewick(newick);
  const nodes = layout(root, W, H);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-text-primary font-semibold">Phylogenetic Tree</h3>
        <button onClick={() => exportSvgPng(svgRef.current, "phylotree.png")}
          className="btn-ghost text-xs px-2 py-1">Export PNG</button>
      </div>
      <div className="glass-card overflow-hidden p-2">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full">
          {nodes.map((n, i) =>
            n.children.map((child, j) => (
              <g key={`${i}-${j}`}>
                <line x1={n.x} y1={child.y} x2={child.x} y2={child.y} stroke="rgba(0,245,212,0.3)" strokeWidth={1.5} />
                <line x1={n.x} y1={n.y} x2={n.x} y2={child.y} stroke="rgba(0,245,212,0.3)" strokeWidth={1.5} />
              </g>
            ))
          )}

          {nodes.map((n, i) => (
            <g key={i}>
              <circle cx={n.x} cy={n.y} r={n.children.length ? 3 : 4}
                fill={n.children.length ? "rgba(0,245,212,0.5)" : "#00F5D4"} />
              {!n.children.length && n.name && (
                <text x={n.x + 8} y={n.y + 4} fill="rgba(255,255,255,0.7)" fontSize={10}>
                  {n.name.replace(/_/g, " ").slice(0, 24)}
                </text>
              )}
            </g>
          ))}
        </svg>
      </div>
      <p className="text-xs text-text-muted">Neighbor-joining tree from multiple sequence alignment (EBI Clustal Omega).</p>
    </div>
  );
}

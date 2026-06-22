"use client";
import { useEffect, useState, useRef } from "react";
import { exportSvgPng } from "@/lib/export-utils";

type NewickNode = {
  name: string;
  length: number;
  children: NewickNode[];
};

function parseNewick(s: string): NewickNode {
  const stack: NewickNode[] = [];
  let node: NewickNode = { name: "", length: 0, children: [] };
  let i = 0;

  while (i < s.length) {
    const ch = s[i];
    if (ch === "(") {
      const child: NewickNode = { name: "", length: 0, children: [] };
      node.children.push(child);
      stack.push(node);
      node = child;
    } else if (ch === ",") {
      const sibling: NewickNode = { name: "", length: 0, children: [] };
      stack[stack.length - 1].children.push(sibling);
      node = sibling;
    } else if (ch === ")") {
      node = stack.pop()!;
    } else if (ch === ":") {
      i++;
      let num = "";
      while (i < s.length && /[0-9.eE+\-]/.test(s[i])) { num += s[i]; i++; }
      node.length = parseFloat(num) || 0;
      continue;
    } else if (ch !== ";" && ch !== " ") {
      let name = "";
      while (i < s.length && !["(", ")", ",", ":", ";", " "].includes(s[i])) { name += s[i]; i++; }
      node.name = name.trim();
      continue;
    }
    i++;
  }
  return node;
}

type LayoutNode = {
  name: string;
  length: number;
  children: LayoutNode[];
  x: number;
  y: number;
  depth: number;
  isBootstrap: boolean;
};

function layout(root: NewickNode, drawW: number, drawH: number) {
  const leaves: NewickNode[] = [];
  const collect = (n: NewickNode) => {
    if (!n.children.length) leaves.push(n);
    else n.children.forEach(collect);
  };
  collect(root);

  const leafSpacing = drawH / (leaves.length + 1);
  let leafIdx = 0;
  const allNodes: LayoutNode[] = [];
  const hasBranchLengths = leaves.some(l => l.length > 0);

  function assignY(n: NewickNode, depth: number): LayoutNode {
    const isNum = n.children.length > 0 && /^\d+$/.test(n.name);
    const ln: LayoutNode = {
      name: isNum ? "" : n.name,
      length: n.length,
      children: [],
      x: depth,
      y: 0,
      depth,
      isBootstrap: isNum,
    };
    if (!n.children.length) {
      ln.y = (++leafIdx) * leafSpacing;
    } else {
      const kids = n.children.map(c => assignY(c, depth + c.length));
      ln.children = kids;
      ln.y = (kids[0].y + kids[kids.length - 1].y) / 2;
    }
    allNodes.push(ln);
    return ln;
  }

  const rootLaid = assignY(root, 0);
  const maxDepth = Math.max(...allNodes.map(n => n.depth), 0.01);
  const scaleX = maxDepth > 0 ? (d: number) => 20 + (d / maxDepth) * drawW : () => 20;

  const nodes: LayoutNode[] = [];
  const setPos = (n: LayoutNode) => {
    n.x = scaleX(n.depth);
    nodes.push(n);
    n.children.forEach(setPos);
  };
  setPos(rootLaid);

  // Fallback: if no branch lengths, make a uniform cladogram
  if (!hasBranchLengths) {
    const depthMap = new Map<number, number>();
    nodes.forEach(n => {
      const d = Math.round(n.depth * 10);
      depthMap.set(d, (depthMap.get(d) || 0) + 1);
    });
    const maxDepthLevel = Math.max(...Array.from(depthMap.keys()), 1);
    nodes.forEach(n => {
      n.x = 20 + (n.depth / maxDepthLevel) * drawW;
    });
  }

  return { nodes, root: rootLaid, maxDepth: hasBranchLengths ? maxDepth : 0 };
}

export function PhyloTreeViewer({ jobId, newick: propNewick }: { jobId?: string; newick?: string }) {
  const [newick, setNewick] = useState<string | null>(propNewick ?? null);
  const [loading, setLoading] = useState(!propNewick);
  const [error, setError] = useState<string | null>(null);
  const [layoutMode, setLayoutMode] = useState<"rectangular" | "circular">("rectangular");
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

  const W = 700, H = Math.max(400, Math.min(800, (newick.split("\n").length + 2) * 22));
  const margin = { top: 20, right: 140, bottom: 40, left: 20 };
  const drawW = W - margin.left - margin.right;
  const drawH = H - margin.top - margin.bottom;

  const root = parseNewick(newick);
  const { nodes, maxDepth } = layout(root, drawW, drawH);

  const scaleBarLen = maxDepth > 0 ? (maxDepth > 1 ? 1 : Math.pow(10, Math.floor(Math.log10(maxDepth)))) : maxDepth;
  const scaleBarPx = (scaleBarLen / (maxDepth || 1)) * drawW;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-text-primary font-semibold">Phylogenetic Tree</h3>
          <div className="flex gap-1 bg-surface-1 rounded-lg p-0.5">
            <button onClick={() => setLayoutMode("rectangular")}
              className={`px-2.5 py-1 text-xs rounded-md transition ${layoutMode === "rectangular" ? "bg-accent-cyan/20 text-accent-cyan" : "text-text-muted hover:text-text-primary"}`}>
              Rectangular
            </button>
            <button onClick={() => setLayoutMode("circular")}
              className={`px-2.5 py-1 text-xs rounded-md transition ${layoutMode === "circular" ? "bg-accent-cyan/20 text-accent-cyan" : "text-text-muted hover:text-text-primary"}`}>
              Circular
            </button>
          </div>
        </div>
        <button onClick={() => exportSvgPng(svgRef.current, "phylotree.png")}
          className="btn-ghost text-xs px-2 py-1">Export PNG</button>
      </div>

      <div className="glass-card overflow-hidden p-2">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ background: "#04040A" }}>
          {layoutMode === "rectangular" ? (
            <RectangularTree nodes={nodes} margin={margin} maxDepth={maxDepth}
              scaleBarLen={scaleBarLen} scaleBarPx={scaleBarPx} W={W} H={H} drawW={drawW} drawH={drawH} />
          ) : (
            <CircularTree nodes={nodes} drawW={drawW} drawH={drawH} margin={margin} />
          )}
        </svg>
      </div>
      {maxDepth > 0 && (
        <p className="text-xs text-text-muted">
          Branch lengths represent substitutions per site. Scale bar: {scaleBarLen.toFixed(3)}.
        </p>
      )}
    </div>
  );
}

function RectangularTree({ nodes, margin, maxDepth, scaleBarLen, scaleBarPx, W, H, drawW, drawH }: {
  nodes: LayoutNode[]; margin: any; maxDepth: number; scaleBarLen: number; scaleBarPx: number; W: number; H: number; drawW: number; drawH: number;
}) {
  const lines: JSX.Element[] = [];
  const labels: JSX.Element[] = [];
  const bootstrapLabels: JSX.Element[] = [];
  const doneInternal = new Set<number>();

  nodes.forEach(n => {
    n.children.forEach((child, j) => {
      const key = `${n.y}-${j}`;
      lines.push(
        <line key={`h-${key}`} x1={n.x} y1={child.y + margin.top} x2={child.x} y2={child.y + margin.top}
          stroke="rgba(0,245,212,0.35)" strokeWidth={1.5} />
      );
    });

    if (n.children.length > 0 && !doneInternal.has(n.y)) {
      doneInternal.add(n.y);
      const firstY = n.children[0].y + margin.top;
      const lastY = n.children[n.children.length - 1].y + margin.top;
      lines.push(
        <line key={`v-${n.y}`} x1={n.x} y1={firstY} x2={n.x} y2={lastY}
          stroke="rgba(0,245,212,0.35)" strokeWidth={1.5} />
      );
    }
  });

  nodes.forEach((n, i) => {
    const cy = n.y + margin.top;
    const isLeaf = !n.children.length;
    lines.push(
      <circle key={`c-${i}`} cx={n.x} cy={cy} r={isLeaf ? 3.5 : 3}
        fill={isLeaf ? "#00F5D4" : "rgba(0,245,212,0.4)"} />
    );
    if (isLeaf && n.name) {
      labels.push(
        <text key={`l-${i}`} x={n.x + 8} y={cy + 4}
          fill="rgba(255,255,255,0.8)" fontSize={11} fontFamily="monospace">
          {n.name.replace(/_/g, " ")}
        </text>
      );
    }
    if (n.children.length > 0 && n.name && /^\d+$/.test(n.name)) {
      bootstrapLabels.push(
        <text key={`b-${i}`} x={n.x - 4} y={cy - 6}
          fill="#F59E0B" fontSize={9} textAnchor="end" fontWeight="bold">
          {n.name}%
        </text>
      );
    }
  });

  // Scale bar
  const scaleY = H - 10;
  const scaleX = margin.left;
  const scaleBar: JSX.Element[] = [];
  if (maxDepth > 0 && scaleBarPx > 20) {
    scaleBar.push(
      <line key="sb-line" x1={scaleX} y1={scaleY} x2={scaleX + Math.min(scaleBarPx, drawW)} y2={scaleY}
        stroke="rgba(255,255,255,0.5)" strokeWidth={1.5} />
    );
    scaleBar.push(
      <line key="sb-tick-l" x1={scaleX} y1={scaleY - 4} x2={scaleX} y2={scaleY + 4}
        stroke="rgba(255,255,255,0.5)" strokeWidth={1.5} />
    );
    scaleBar.push(
      <line key="sb-tick-r" x1={scaleX + Math.min(scaleBarPx, drawW)} y1={scaleY - 4}
        x2={scaleX + Math.min(scaleBarPx, drawW)} y2={scaleY + 4}
        stroke="rgba(255,255,255,0.5)" strokeWidth={1.5} />
    );
    scaleBar.push(
      <text key="sb-label" x={scaleX + Math.min(scaleBarPx, drawW) / 2} y={scaleY - 8}
        fill="rgba(255,255,255,0.5)" fontSize={10} textAnchor="middle">
        {scaleBarLen.toFixed(3)}
      </text>
    );
  }

  return <>{lines}{bootstrapLabels}{labels}{scaleBar}</>;
}

function CircularTree({ nodes, drawW, drawH, margin }: {
  nodes: LayoutNode[]; drawW: number; drawH: number; margin: any;
}) {
  const cx = drawW / 2 + margin.left;
  const cy = drawH / 2 + margin.top;
  const radius = Math.min(drawW, drawH) / 2 - 30;
  const maxDepth = Math.max(...nodes.map(n => n.depth), 1);

  const lines: JSX.Element[] = [];
  const labels: JSX.Element[] = [];
  const doneInternal = new Set<number>();

  function polar(r: number, angle: number) {
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  }

  nodes.forEach(n => {
    const angle = (n.y / (drawH + margin.top + margin.bottom)) * Math.PI * 2;
    const r = (n.depth / maxDepth) * radius;
    const pos = polar(r, angle);

    n.children.forEach((child, j) => {
      const childAngle = (child.y / (drawH + margin.top + margin.bottom)) * Math.PI * 2;
      const childR = (child.depth / maxDepth) * radius;
      const childPos = polar(childR, childAngle);
      lines.push(
        <line key={`ch-${n.y}-${j}`} x1={pos.x} y1={pos.y} x2={childPos.x} y2={childPos.y}
          stroke="rgba(0,245,212,0.3)" strokeWidth={1.2} />
      );
    });

    if (n.children.length > 0 && !doneInternal.has(n.y)) {
      doneInternal.add(n.y);
      // Draw arc connecting children
      const firstAngle = (n.children[0].y / (drawH + margin.top + margin.bottom)) * Math.PI * 2;
      const lastAngle = (n.children[n.children.length - 1].y / (drawH + margin.top + margin.bottom)) * Math.PI * 2;
      if (lastAngle - firstAngle < Math.PI) {
        const arcR = (n.depth / maxDepth) * radius;
        lines.push(
          <path key={`arc-${n.y}`}
            d={`M ${polar(arcR, firstAngle).x} ${polar(arcR, firstAngle).y} A ${arcR} ${arcR} 0 0 1 ${polar(arcR, lastAngle).x} ${polar(arcR, lastAngle).y}`}
            fill="none" stroke="rgba(0,245,212,0.3)" strokeWidth={1.2} />
        );
      }
    }
  });

  nodes.forEach((n, i) => {
    const angle = (n.y / (drawH + margin.top + margin.bottom)) * Math.PI * 2;
    const r = (n.depth / maxDepth) * radius;
    const pos = polar(r, angle);
    const isLeaf = !n.children.length;
    lines.push(
      <circle key={`c-${i}`} cx={pos.x} cy={pos.y} r={isLeaf ? 3 : 2.5}
        fill={isLeaf ? "#00F5D4" : "rgba(0,245,212,0.4)"} />
    );
    if (isLeaf && n.name) {
      const labelR = r + 12;
      const labelPos = polar(labelR, angle);
      labels.push(
        <text key={`l-${i}`} x={labelPos.x} y={labelPos.y}
          fill="rgba(255,255,255,0.8)" fontSize={10} fontFamily="monospace"
          textAnchor={angle > Math.PI / 2 && angle < Math.PI * 1.5 ? "end" : "start"}
          transform={angle > Math.PI / 2 && angle < Math.PI * 1.5 ? `rotate(${angle * 180 / Math.PI + 180}, ${labelPos.x}, ${labelPos.y})` : `rotate(${angle * 180 / Math.PI}, ${labelPos.x}, ${labelPos.y})`}>
          {n.name.replace(/_/g, " ")}
        </text>
      );
    }
  });

  return <>{lines}{labels}</>;
}

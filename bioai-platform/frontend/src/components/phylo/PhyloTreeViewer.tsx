'use client'

/**
 * PhyloTreeViewer
 *
 * Renders a phylogenetic tree from a Newick string.
 * Supports rectangular (default) and circular layout.
 * Exports: SVG file, PNG (via canvas), raw Newick download.
 *
 * Props:
 *   newick       – Newick format tree string (required)
 *   method       – 'nj' | 'ml' | 'upgma'  (shows badge)
 *   alignment    – FASTA alignment string  (shows collapsible section)
 *   sequenceType – 'protein' | 'dna'
 */

import { useCallback, useMemo, useRef, useState } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface TreeNode {
  name: string
  length: number
  bootstrap: number | null
  children: TreeNode[]
  x: number
  y: number
  px: number
  py: number
  angle?: number
  radius?: number
}

type Layout = 'rectangular' | 'circular'

export interface PhyloTreeViewerProps {
  newick: string
  method?: 'nj' | 'ml' | 'upgma'
  alignment?: string
  sequenceType?: 'protein' | 'dna'
}

// ─── Newick parser ────────────────────────────────────────────────────────────

function parseNewick(s: string): TreeNode {
  const stack: TreeNode[] = []
  let cur: TreeNode = makeNode()
  let i = 0
  const n = s.length

  while (i < n) {
    const ch = s[i]

    if (ch === '(') {
      const child = makeNode()
      child.px = cur.px; child.py = cur.py
      cur.children.push(child)
      stack.push(cur)
      cur = child
      i++
    } else if (ch === ',') {
      const parent = stack[stack.length - 1]
      const sibling = makeNode()
      parent.children.push(sibling)
      cur = sibling
      i++
    } else if (ch === ')') {
      cur = stack.pop()!
      i++
      while (i < n && s[i] === ' ') i++
      if (i < n && s[i] !== ':' && s[i] !== ',' && s[i] !== ')' && s[i] !== ';' && s[i] !== '[') {
        const [label, ni] = readToken(s, i)
        i = ni
        const num = parseFloat(label)
        if (!isNaN(num) && label.trim() !== '') {
          cur.bootstrap = num
        } else {
          cur.name = label
        }
      }
      if (i < n && s[i] === '[') {
        while (i < n && s[i] !== ']') i++
        i++
      }
      if (i < n && s[i] === ':') {
        i++
        const [lenStr, ni] = readNumber(s, i)
        cur.length = parseFloat(lenStr) || 0
        i = ni
      }
    } else if (ch === ':') {
      i++
      const [lenStr, ni] = readNumber(s, i)
      cur.length = parseFloat(lenStr) || 0
      i = ni
    } else if (ch === ';' || ch === '\n' || ch === '\r') {
      i++
    } else {
      if (ch === "'") {
        i++
        let name = ''
        while (i < n && s[i] !== "'") { name += s[i]; i++ }
        cur.name = name
        i++
      } else {
        const [name, ni] = readToken(s, i)
        cur.name = name
        i = ni
      }
    }
  }
  return cur
}

function makeNode(): TreeNode {
  return { name: '', length: 0, bootstrap: null, children: [], x: 0, y: 0, px: 0, py: 0 }
}

function readToken(s: string, i: number): [string, number] {
  let tok = ''
  while (i < s.length && !'(),;:['.includes(s[i])) { tok += s[i]; i++ }
  return [tok.trim(), i]
}

function readNumber(s: string, i: number): [string, number] {
  let tok = ''
  while (i < s.length && '0123456789.-eE+'.includes(s[i])) { tok += s[i]; i++ }
  return [tok, i]
}

// ─── Rectangular layout ───────────────────────────────────────────────────────

const SVG_W  = 720
const SVG_PAD = { top: 20, right: 160, bottom: 40, left: 20 }

function buildRectangularLayout(root: TreeNode): { nodes: TreeNode[]; height: number; maxDepth: number } {
  const nodes: TreeNode[] = []
  let leafIdx = 0

  function countLeaves(n: TreeNode): number {
    if (!n.children.length) return 1
    return n.children.reduce((s, c) => s + countLeaves(c), 0)
  }
  const totalLeaves = countLeaves(root)
  const rowH  = Math.max(18, Math.min(26, 600 / totalLeaves))
  const drawH = totalLeaves * rowH
  const drawW = SVG_W - SVG_PAD.left - SVG_PAD.right

  function hasBranchLengths(n: TreeNode): boolean {
    return n.length > 0 || n.children.some(hasBranchLengths)
  }
  const useLengths = hasBranchLengths(root)

  function maxDepth(n: TreeNode, d: number): number {
    if (!n.children.length) return d + n.length
    return Math.max(...n.children.map(c => maxDepth(c, d + n.length)))
  }
  const totalDepth = useLengths ? maxDepth(root, 0) : 0

  function assignPositions(n: TreeNode, depth: number, px: number, py: number): void {
    nodes.push(n)
    const x = useLengths && totalDepth > 0
      ? SVG_PAD.left + (depth / totalDepth) * drawW
      : SVG_PAD.left + depth * (drawW / (getMaxDepthSteps(root) || 1))
    n.px = px; n.py = py

    if (!n.children.length) {
      n.x = x
      n.y = SVG_PAD.top + leafIdx * rowH + rowH / 2
      leafIdx++
    } else {
      n.children.forEach(c => assignPositions(c, depth + (useLengths ? c.length : 1), x, 0))
      n.y = (n.children[0].y + n.children[n.children.length - 1].y) / 2
      n.x = x
      n.children.forEach(c => { c.px = n.x; c.py = n.y })
    }
  }

  assignPositions(root, 0, SVG_PAD.left, SVG_PAD.top + drawH / 2)
  root.px = root.x; root.py = root.y

  return { nodes, height: drawH + SVG_PAD.top + SVG_PAD.bottom, maxDepth: totalDepth }
}

function getMaxDepthSteps(n: TreeNode, d = 0): number {
  if (!n.children.length) return d
  return Math.max(...n.children.map(c => getMaxDepthSteps(c, d + 1)))
}

// ─── Circular layout ──────────────────────────────────────────────────────────

const CIRC_R    = 280
const CIRC_CX   = 380
const CIRC_CY   = 380
const CIRC_SIZE = 760

function buildCircularLayout(root: TreeNode): TreeNode[] {
  const nodes: TreeNode[] = []

  function countLeaves(n: TreeNode): number {
    return n.children.length ? n.children.reduce((s, c) => s + countLeaves(c), 0) : 1
  }
  const total = countLeaves(root)
  let leafIdx = 0

  function hasBranchLengths(n: TreeNode): boolean {
    return n.length > 0 || n.children.some(hasBranchLengths)
  }
  const useLengths = hasBranchLengths(root)

  function maxCumDist(n: TreeNode, d: number): number {
    if (!n.children.length) return d + (useLengths ? n.length : 1)
    return Math.max(...n.children.map(c => maxCumDist(c, d + (useLengths ? c.length : 1))))
  }
  const maxDist = maxCumDist(root, 0) || 1

  function assignAngles(n: TreeNode): number {
    if (!n.children.length) {
      n.angle = (leafIdx / total) * 2 * Math.PI
      leafIdx++
      return n.angle!
    }
    const childAngles = n.children.map(assignAngles)
    n.angle = (Math.min(...childAngles) + Math.max(...childAngles)) / 2
    return n.angle!
  }

  function assignRadii(n: TreeNode, cumDist: number): void {
    n.radius = (cumDist / maxDist) * CIRC_R
    n.children.forEach(c => assignRadii(c, cumDist + (useLengths ? c.length : 1)))
  }

  function toCartesian(n: TreeNode, parent: TreeNode | null): void {
    nodes.push(n)
    n.x = CIRC_CX + n.radius! * Math.cos(n.angle!)
    n.y = CIRC_CY + n.radius! * Math.sin(n.angle!)
    n.px = parent ? parent.x : n.x
    n.py = parent ? parent.y : n.y
    n.children.forEach(c => toCartesian(c, n))
  }

  assignAngles(root)
  assignRadii(root, 0)
  toCartesian(root, null)
  return nodes
}

// ─── Bootstrap colour scale ────────────────────────────────────────────────────

function bootstrapColour(val: number): string {
  if (val >= 90) return '#00F5D4'
  if (val >= 70) return '#a3e635'
  if (val >= 50) return '#fb923c'
  return '#f87171'
}

// ─── SVG renderers ────────────────────────────────────────────────────────────

function RectangularTree({ nodes, svgH, maxDepth }: { nodes: TreeNode[]; svgH: number; maxDepth: number }) {
  const drawW = SVG_W - SVG_PAD.left - SVG_PAD.right

  return (
    <>
      {nodes.map((n, i) => {
        if (n.px === n.x && n.py === n.y) return null
        return (
          <g key={`b-${i}`}>
            <line x1={n.px} y1={n.py} x2={n.px} y2={n.y}
              stroke="#334155" strokeWidth={1.2} />
            <line x1={n.px} y1={n.y} x2={n.x} y2={n.y}
              stroke="#475569" strokeWidth={1.5} />
          </g>
        )
      })}

      {nodes.map((n, i) => {
        const isLeaf = n.children.length === 0
        return (
          <g key={`n-${i}`}>
            {isLeaf ? (
              <>
                <circle cx={n.x} cy={n.y} r={3} fill="#00F5D4" opacity={0.8} />
                <text x={n.x + 8} y={n.y + 4} fontSize={11} fill="#94a3b8"
                  fontFamily="'JetBrains Mono', monospace">
                  {n.name}
                </text>
              </>
            ) : (
              <>
                <circle cx={n.x} cy={n.y} r={2.5} fill="#475569" />
                {n.bootstrap !== null && n.bootstrap >= 50 && (
                  <text x={n.x - 4} y={n.y - 5} fontSize={9}
                    fill={bootstrapColour(n.bootstrap)} textAnchor="end"
                    fontFamily="sans-serif">
                    {Math.round(n.bootstrap)}
                  </text>
                )}
              </>
            )}
          </g>
        )
      })}

      {maxDepth > 0 && (() => {
        const scaleVal = parseFloat((maxDepth / 5).toPrecision(1))
        const scaleW   = (scaleVal / maxDepth) * drawW
        const bx = SVG_PAD.left
        const by = svgH - SVG_PAD.bottom + 10
        return (
          <g>
            <line x1={bx} y1={by} x2={bx + scaleW} y2={by} stroke="#64748b" strokeWidth={1.5} />
            <line x1={bx}          y1={by - 4} x2={bx}          y2={by + 4} stroke="#64748b" strokeWidth={1.5} />
            <line x1={bx + scaleW} y1={by - 4} x2={bx + scaleW} y2={by + 4} stroke="#64748b" strokeWidth={1.5} />
            <text x={bx + scaleW / 2} y={by + 14} fontSize={10} fill="#64748b"
              textAnchor="middle" fontFamily="sans-serif">
              {scaleVal} substitutions/site
            </text>
          </g>
        )
      })()}
    </>
  )
}

function CircularTree({ nodes }: { nodes: TreeNode[] }) {
  return (
    <>
      {nodes.map((n, i) => {
        if (n.px === n.x && n.py === n.y) return null
        return (
          <line key={`b-${i}`}
            x1={n.px} y1={n.py} x2={n.x} y2={n.y}
            stroke="#475569" strokeWidth={1.4} />
        )
      })}

      {nodes.filter(n => n.children.length > 0).map((n, i) => {
        const r = n.radius!
        if (r < 1 || n.children.length < 2) return null
        const angles = n.children.map(c => c.angle!)
        const a0 = Math.min(...angles)
        const a1 = Math.max(...angles)
        const x0 = CIRC_CX + r * Math.cos(a0)
        const y0 = CIRC_CY + r * Math.sin(a0)
        const x1 = CIRC_CX + r * Math.cos(a1)
        const y1 = CIRC_CY + r * Math.sin(a1)
        const largeArc = (a1 - a0) > Math.PI ? 1 : 0
        return (
          <path key={`arc-${i}`}
            d={`M ${x0} ${y0} A ${r} ${r} 0 ${largeArc} 1 ${x1} ${y1}`}
            fill="none" stroke="#334155" strokeWidth={1.2} />
        )
      })}

      {nodes.map((n, i) => {
        const isLeaf = n.children.length === 0
        const angle  = n.angle ?? 0
        const deg    = (angle * 180) / Math.PI
        const flip   = deg > 90 && deg < 270
        const labelX = CIRC_CX + (n.radius! + 10) * Math.cos(angle)
        const labelY = CIRC_CY + (n.radius! + 10) * Math.sin(angle)

        return (
          <g key={`n-${i}`}
            transform={`rotate(${deg - (flip ? 180 : 0)}, ${CIRC_CX + n.radius! * Math.cos(angle)}, ${CIRC_CY + n.radius! * Math.sin(angle)})`}>
            {isLeaf ? (
              <>
                <circle cx={n.x} cy={n.y} r={3} fill="#00F5D4" opacity={0.8} />
                <text
                  x={labelX} y={labelY + 4}
                  fontSize={10} fill="#94a3b8"
                  fontFamily="'JetBrains Mono', monospace"
                  textAnchor={flip ? 'end' : 'start'}
                  transform={`rotate(${-(deg - (flip ? 180 : 0))}, ${labelX}, ${labelY})`}
                >
                  {n.name}
                </text>
              </>
            ) : (
              <>
                <circle cx={n.x} cy={n.y} r={2.5} fill="#475569" />
                {n.bootstrap !== null && n.bootstrap >= 50 && (
                  <text x={n.x} y={n.y - 6} fontSize={8}
                    fill={bootstrapColour(n.bootstrap)} textAnchor="middle">
                    {Math.round(n.bootstrap)}
                  </text>
                )}
              </>
            )}
          </g>
        )
      })}
    </>
  )
}

// ─── Export helpers ───────────────────────────────────────────────────────────

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a   = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

function exportSVG(svgEl: SVGSVGElement, filename: string) {
  const src = '<?xml version="1.0" encoding="UTF-8"?>\n' +
    new XMLSerializer().serializeToString(svgEl)
  downloadBlob(new Blob([src], { type: 'image/svg+xml' }), filename)
}

function exportPNG(svgEl: SVGSVGElement, filename: string) {
  const { width, height } = svgEl.viewBox.baseVal
  const scale  = 2
  const canvas = Object.assign(document.createElement('canvas'), {
    width: width * scale, height: height * scale,
  })
  const ctx  = canvas.getContext('2d')!
  const img  = new Image()
  const data = 'data:image/svg+xml;base64,' +
    btoa(unescape(encodeURIComponent(new XMLSerializer().serializeToString(svgEl))))
  img.onload = () => {
    ctx.fillStyle = '#04040A'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.scale(scale, scale)
    ctx.drawImage(img, 0, 0)
    canvas.toBlob(b => b && downloadBlob(b, filename), 'image/png')
  }
  img.src = data
}

// ─── Method badge ─────────────────────────────────────────────────────────────

const METHOD_META = {
  nj:    { label: 'Neighbor-Joining', colour: 'text-accent-cyan  border-accent-cyan/40  bg-accent-cyan/10' },
  ml:    { label: 'Maximum Likelihood', colour: 'text-violet-400  border-violet-400/40  bg-violet-400/10' },
  upgma: { label: 'UPGMA', colour: 'text-amber-400  border-amber-400/40  bg-amber-400/10' },
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function PhyloTreeViewer({
  newick,
  method,
  alignment,
  sequenceType = 'protein',
}: PhyloTreeViewerProps) {
  const [layout, setLayout]         = useState<Layout>('rectangular')
  const [showAlignment, setShowAln] = useState(false)
  const [showRaw, setShowRaw]       = useState(false)
  const svgRef                      = useRef<SVGSVGElement>(null)

  const treeData = useMemo(() => {
    try {
      const root = parseNewick(newick)
      if (layout === 'rectangular') {
        const { nodes, height, maxDepth } = buildRectangularLayout(root)
        return { nodes, height, maxDepth, error: null }
      } else {
        const nodes = buildCircularLayout(root)
        return { nodes, height: CIRC_SIZE, maxDepth: 0, error: null }
      }
    } catch (e) {
      return { nodes: [], height: 400, maxDepth: 0, error: String(e) }
    }
  }, [newick, layout])

  const filename = `phylo_tree_${method ?? 'tree'}`

  const handleExportSVG = useCallback(() => {
    if (svgRef.current) exportSVG(svgRef.current, `${filename}.svg`)
  }, [filename])

  const handleExportPNG = useCallback(() => {
    if (svgRef.current) exportPNG(svgRef.current, `${filename}.png`)
  }, [filename])

  const handleExportNewick = useCallback(() => {
    downloadBlob(new Blob([newick], { type: 'text/plain' }), `${filename}.nwk`)
  }, [newick, filename])

  if (treeData.error) {
    return (
      <div className="glass-card p-6 text-red-400">
        <p className="font-medium mb-1">Failed to parse Newick string</p>
        <pre className="text-xs opacity-70 overflow-auto">{treeData.error}</pre>
        <pre className="text-xs opacity-40 mt-2 overflow-auto">{newick.slice(0, 200)}</pre>
      </div>
    )
  }

  return (
    <div className="space-y-4">

      <div className="flex flex-wrap items-center gap-3">

        {method && (
          <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${METHOD_META[method].colour}`}>
            {METHOD_META[method].label}
          </span>
        )}

        <div className="flex gap-1 bg-surface-1 rounded-lg p-1 border border-glass-border">
          {(['rectangular', 'circular'] as Layout[]).map(l => (
            <button key={l} onClick={() => setLayout(l)}
              className={`text-xs px-3 py-1 rounded-md transition-colors capitalize ${
                layout === l
                  ? 'bg-accent-cyan/20 text-accent-cyan'
                  : 'text-text-secondary hover:text-text-primary'
              }`}>
              {l}
            </button>
          ))}
        </div>

        {method === 'ml' && (
          <div className="flex items-center gap-2 text-[10px] text-text-secondary">
            <span className="font-medium">Bootstrap:</span>
            {[['≥90', '#00F5D4'], ['70–89', '#a3e635'], ['50–69', '#fb923c'], ['<50', '#f87171']]
              .map(([label, colour]) => (
                <span key={label} className="flex items-center gap-0.5">
                  <span style={{ color: colour }}>■</span> {label}
                </span>
              ))}
          </div>
        )}

        <div className="flex gap-2 ml-auto">
          {[
            { label: 'SVG',    fn: handleExportSVG },
            { label: 'PNG',    fn: handleExportPNG },
            { label: 'Newick', fn: handleExportNewick },
          ].map(({ label, fn }) => (
            <button key={label} onClick={fn}
              className="text-xs px-3 py-1.5 rounded-lg border border-glass-border
                text-text-secondary hover:text-text-primary hover:border-accent-cyan/40
                transition-colors">
              ↓ {label}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-surface-1 rounded-xl border border-glass-border overflow-x-auto">
        <svg
          ref={svgRef}
          viewBox={layout === 'rectangular'
            ? `0 0 ${SVG_W} ${treeData.height}`
            : `0 0 ${CIRC_SIZE} ${CIRC_SIZE}`}
          width="100%"
          style={{ maxHeight: '70vh', background: '#04040A' }}
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width="100%" height="100%" fill="#04040A" />

          {layout === 'rectangular' ? (
            <RectangularTree
              nodes={treeData.nodes}
              svgH={treeData.height}
              maxDepth={treeData.maxDepth}
            />
          ) : (
            <CircularTree nodes={treeData.nodes} />
          )}
        </svg>
      </div>

      <p className="text-text-secondary text-xs">
        {treeData.nodes.filter(n => n.children.length === 0).length} taxa ·{' '}
        {sequenceType === 'protein' ? 'protein' : 'nucleotide'} sequences
      </p>

      {alignment && (
        <div className="border border-glass-border rounded-xl overflow-hidden">
          <button
            onClick={() => setShowAln(v => !v)}
            className="w-full flex items-center justify-between px-4 py-3
              text-text-secondary hover:text-text-primary transition-colors text-sm"
          >
            <span>Multiple Sequence Alignment</span>
            <span className="text-xs opacity-60">{showAlignment ? '▲ hide' : '▼ show'}</span>
          </button>
          {showAlignment && (
            <pre className="overflow-auto p-4 text-[11px] font-mono text-emerald-400
              bg-surface-1 max-h-60 leading-relaxed">
              {alignment}
            </pre>
          )}
        </div>
      )}

      <div className="border border-glass-border rounded-xl overflow-hidden">
        <button
          onClick={() => setShowRaw(v => !v)}
          className="w-full flex items-center justify-between px-4 py-3
            text-text-secondary hover:text-text-primary transition-colors text-sm"
        >
          <span>Raw Newick</span>
          <span className="text-xs opacity-60">{showRaw ? '▲ hide' : '▼ show'}</span>
        </button>
        {showRaw && (
          <pre className="overflow-auto p-4 text-[11px] font-mono text-text-secondary
            bg-surface-1 max-h-40 whitespace-pre-wrap break-all">
            {newick}
          </pre>
        )}
      </div>
    </div>
  )
}

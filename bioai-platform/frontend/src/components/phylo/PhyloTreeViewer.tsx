'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface TreeNode {
  id: number
  name: string
  length: number
  bootstrap: number | null
  children: TreeNode[]
  parent: TreeNode | null
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
  let nextId = 0
  const makeNode = (): TreeNode => ({
    id: nextId++, name: '', length: 0, bootstrap: null,
    children: [], parent: null,
    x: 0, y: 0, px: 0, py: 0,
  })
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
      child.parent = cur
      cur = child
      i++
    } else if (ch === ',') {
      const parent = stack[stack.length - 1]
      const sibling = makeNode()
      parent.children.push(sibling)
      sibling.parent = parent
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

// ─── Tree helpers ─────────────────────────────────────────────────────────────

function countLeaves(n: TreeNode): number {
  if (!n.children.length) return 1
  return n.children.reduce((s, c) => s + countLeaves(c), 0)
}

function pruneTree(node: TreeNode, collapsed: Set<number>): TreeNode {
  if (collapsed.has(node.id) && node.children.length > 0) {
    return { ...node, id: node.id, children: [], name: `+${countLeaves(node)}`, parent: null }
  }
  const children = node.children.map(c => pruneTree(c, collapsed))
  const pruned = { ...node, children, parent: null }
  children.forEach(c => { c.parent = pruned })
  return pruned
}

function computePathSet(nodes: TreeNode[], targetId: number | null): Set<number> {
  if (targetId === null) return new Set()
  const map = new Map<number, TreeNode>()
  for (const n of nodes) map.set(n.id, n)
  const path = new Set<number>()
  let id: number | undefined = targetId
  while (id !== undefined) {
    path.add(id)
    const node = map.get(id)
    id = node?.parent?.id
  }
  return path
}

function findNodeById(nodes: TreeNode[], id: number): TreeNode | null {
  for (const n of nodes) {
    if (n.id === id) return n
    if (n.children.length) {
      const found = findNodeById(n.children, id)
      if (found) return found
    }
  }
  return null
}

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v))
}

// ─── Rectangular layout ───────────────────────────────────────────────────────

const SVG_W  = 720
const SVG_PAD = { top: 20, right: 160, bottom: 40, left: 20 }

function buildRectangularLayout(root: TreeNode, collapsed: Set<number>):
  { nodes: TreeNode[]; height: number; maxDepth: number; rootNode: TreeNode } {
  const pruned = pruneTree(root, collapsed)
  const nodes: TreeNode[] = []
  let leafIdx = 0

  const totalLeaves = countLeaves(pruned)
  const rowH  = Math.max(18, Math.min(26, 600 / totalLeaves))
  const drawH = totalLeaves * rowH
  const drawW = SVG_W - SVG_PAD.left - SVG_PAD.right

  function hasBranchLengths(n: TreeNode): boolean {
    return n.length > 0 || n.children.some(hasBranchLengths)
  }
  const useLengths = hasBranchLengths(pruned)

  function maxDepth(n: TreeNode, d: number): number {
    if (!n.children.length) return d + n.length
    return Math.max(...n.children.map(c => maxDepth(c, d + n.length)))
  }
  const totalDepth = useLengths ? maxDepth(pruned, 0) : 0

  function getMaxDepthSteps(n: TreeNode, d = 0): number {
    if (!n.children.length) return d
    return Math.max(...n.children.map(c => getMaxDepthSteps(c, d + 1)))
  }

  function assignPositions(n: TreeNode, depth: number, px: number, py: number): void {
    nodes.push(n)
    const x = useLengths && totalDepth > 0
      ? SVG_PAD.left + (depth / totalDepth) * drawW
      : SVG_PAD.left + depth * (drawW / (getMaxDepthSteps(pruned) || 1))
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

  assignPositions(pruned, 0, SVG_PAD.left, SVG_PAD.top + drawH / 2)
  pruned.px = pruned.x; pruned.py = pruned.y

  return { nodes, height: drawH + SVG_PAD.top + SVG_PAD.bottom, maxDepth: totalDepth, rootNode: pruned }
}

// ─── Circular layout ──────────────────────────────────────────────────────────

const CIRC_R    = 280
const CIRC_CX   = 380
const CIRC_CY   = 380
const CIRC_SIZE = 760

function buildCircularLayout(root: TreeNode, collapsed: Set<number>):
  { nodes: TreeNode[]; height: number; maxDepth: number; rootNode: TreeNode } {
  const pruned = pruneTree(root, collapsed)
  const nodes: TreeNode[] = []

  const total = countLeaves(pruned)
  let leafIdx = 0

  function hasBranchLengths(n: TreeNode): boolean {
    return n.length > 0 || n.children.some(hasBranchLengths)
  }
  const useLengths = hasBranchLengths(pruned)

  function maxCumDist(n: TreeNode, d: number): number {
    if (!n.children.length) return d + (useLengths ? n.length : 1)
    return Math.max(...n.children.map(c => maxCumDist(c, d + (useLengths ? c.length : 1))))
  }
  const maxDist = maxCumDist(pruned, 0) || 1

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

  assignAngles(pruned)
  assignRadii(pruned, 0)
  toCartesian(pruned, null)
  return { nodes, height: CIRC_SIZE, maxDepth: 0, rootNode: pruned }
}

// ─── Bootstrap colour scale ────────────────────────────────────────────────────

function bootstrapColour(val: number): string {
  if (val >= 90) return '#00F5D4'
  if (val >= 70) return '#a3e635'
  if (val >= 50) return '#fb923c'
  return '#f87171'
}

// ─── SVG sub-renderers ────────────────────────────────────────────────────────

function RectangularTree({
  nodes, svgH, maxDepth,
  pathSet, selectedId, hoveredId,
  onNodeHover, onNodeClick, onNodeDoubleClick,
}: {
  nodes: TreeNode[]; svgH: number; maxDepth: number
  pathSet: Set<number>; selectedId: number | null; hoveredId: number | null
  onNodeHover: (id: number | null) => void; onNodeClick: (id: number) => void; onNodeDoubleClick: (id: number) => void
}) {
  const hasHover = hoveredId !== null
  const drawW = SVG_W - SVG_PAD.left - SVG_PAD.right

  return (
    <>
      {nodes.map((n, i) => {
        if (n.px === n.x && n.py === n.y) return null
        const onPath = pathSet.has(n.id)
        const dim  = hasHover && !onPath
        const bright = hasHover && onPath
        return (
          <g key={`b-${i}`}>
            <line x1={n.px} y1={n.py} x2={n.px} y2={n.y}
              stroke={bright ? '#00F5D4' : '#334155'}
              strokeWidth={bright ? 2 : dim ? 0.5 : 1.2}
              opacity={dim ? 0.12 : 1} />
            <line x1={n.px} y1={n.y} x2={n.x} y2={n.y}
              stroke={bright ? '#00F5D4' : '#475569'}
              strokeWidth={bright ? 2.5 : dim ? 0.5 : 1.5}
              opacity={dim ? 0.12 : 1} />
            {n.length > 0.001 && (
              <text x={(n.px + n.x) / 2} y={n.y - 5} fontSize={8}
                fill={bright ? '#00F5D4' : '#64748b'}
                opacity={dim ? 0.12 : 0.8}
                textAnchor="middle" fontFamily="sans-serif">
                {n.length.toFixed(4)}
              </text>
            )}
          </g>
        )
      })}

      {nodes.map((n, i) => {
        const isLeaf = n.children.length === 0
        const onPath = pathSet.has(n.id)
        const dim = hasHover && !onPath
        const bright = hasHover && onPath
        const isSelected = selectedId === n.id
        const blTip = n.length > 0 ? `branch length: ${n.length.toFixed(5)}` : ''
        return (
          <g key={`n-${i}`}
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => onNodeHover(n.id)}
            onMouseLeave={() => onNodeHover(null)}
            onClick={(e) => { e.stopPropagation(); onNodeClick(n.id) }}
            onDoubleClick={(e) => { e.stopPropagation(); onNodeDoubleClick(n.id) }}
          >
            {isLeaf ? (
              <>
                <circle cx={n.x} cy={n.y} r={isSelected ? 5 : 3}
                  fill="#00F5D4"
                  opacity={dim ? 0.12 : isSelected ? 1 : 0.8}
                  stroke={isSelected ? '#fff' : 'none'}
                  strokeWidth={isSelected ? 1.5 : 0} />
                <text x={n.x + 8} y={n.y + 4} fontSize={11}
                  fill={bright ? '#00F5D4' : '#94a3b8'}
                  opacity={dim ? 0.12 : 1}
                  fontFamily="'JetBrains Mono', monospace"
                  fontWeight={isSelected ? 'bold' : 'normal'}>
                  {n.name}
                </text>
                <title>{n.name}{blTip ? ` · ${blTip}` : ''}</title>
              </>
            ) : (
              <>
                <circle cx={n.x} cy={n.y} r={isSelected ? 7 : 5}
                  fill={dim ? '#1e293b' : isSelected ? '#00F5D4' : '#1e293b'}
                  stroke={isSelected ? '#fff' : bright ? '#00F5D4' : '#475569'}
                  strokeWidth={isSelected ? 2 : bright ? 2 : 1.5}
                  opacity={dim ? 0.12 : 0.85} />
                {n.bootstrap !== null && n.bootstrap >= 50 && (
                  <text x={n.x - 4} y={n.y - 7} fontSize={9}
                    fill={bootstrapColour(n.bootstrap)} textAnchor="end"
                    fontFamily="sans-serif" fontWeight="bold"
                    opacity={dim ? 0.12 : 1}>
                    {Math.round(n.bootstrap)}
                  </text>
                )}
                <text x={n.x} y={n.y + 4} fontSize={7}
                  fill={bright ? '#00F5D4' : '#64748b'}
                  opacity={dim ? 0.12 : 0.7}
                  textAnchor="middle" fontFamily="sans-serif">
                  {n.name || `N${i}`}
                </text>
                <title>Node {n.name || `N${i}`}{blTip ? ` · ${blTip}` : ''}{n.bootstrap !== null ? ` · bootstrap: ${n.bootstrap}` : ''}</title>
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

function CircularTree({
  nodes, pathSet, selectedId, hoveredId,
  onNodeHover, onNodeClick, onNodeDoubleClick,
}: {
  nodes: TreeNode[]; pathSet: Set<number>; selectedId: number | null; hoveredId: number | null
  onNodeHover: (id: number | null) => void; onNodeClick: (id: number) => void; onNodeDoubleClick: (id: number) => void
}) {
  const hasHover = hoveredId !== null

  return (
    <>
      {nodes.map((n, i) => {
        if (n.px === n.x && n.py === n.y) return null
        const onPath = pathSet.has(n.id)
        const dim  = hasHover && !onPath
        const bright = hasHover && onPath
        const midX = (n.px + n.x) / 2
        const midY = (n.py + n.y) / 2
        return (
          <g key={`b-${i}`}>
            <line x1={n.px} y1={n.py} x2={n.x} y2={n.y}
              stroke={bright ? '#00F5D4' : '#475569'}
              strokeWidth={bright ? 2.5 : dim ? 0.5 : 1.4}
              opacity={dim ? 0.12 : 1} />
            {n.length > 0.001 && (
              <text x={midX} y={midY - 4} fontSize={7}
                fill={bright ? '#00F5D4' : '#64748b'}
                opacity={dim ? 0.12 : 0.8}
                textAnchor="middle" fontFamily="sans-serif">
                {n.length.toFixed(4)}
              </text>
            )}
          </g>
        )
      })}

      {nodes.filter(n => n.children.length > 0).map((n, i) => {
        const r = n.radius!
        if (r < 1 || n.children.length < 2) return null
        const onPath = pathSet.has(n.id)
        const dim  = hasHover && !onPath
        const bright = hasHover && onPath
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
            fill="none" stroke={bright ? '#00F5D4' : '#334155'}
            strokeWidth={bright ? 2 : dim ? 0.5 : 1.2}
            opacity={dim ? 0.12 : 1} />
        )
      })}

      {nodes.map((n, i) => {
        const isLeaf = n.children.length === 0
        const angle  = n.angle ?? 0
        const deg    = (angle * 180) / Math.PI
        const flip   = deg > 90 && deg < 270
        const labelX = CIRC_CX + (n.radius! + 10) * Math.cos(angle)
        const labelY = CIRC_CY + (n.radius! + 10) * Math.sin(angle)
        const onPath = pathSet.has(n.id)
        const dim  = hasHover && !onPath
        const bright = hasHover && onPath
        const isSelected = selectedId === n.id
        const blTip = n.length > 0 ? `branch length: ${n.length.toFixed(5)}` : ''

        return (
          <g key={`n-${i}`}
            transform={`rotate(${deg - (flip ? 180 : 0)}, ${CIRC_CX + n.radius! * Math.cos(angle)}, ${CIRC_CY + n.radius! * Math.sin(angle)})`}
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => onNodeHover(n.id)}
            onMouseLeave={() => onNodeHover(null)}
            onClick={(e) => { e.stopPropagation(); onNodeClick(n.id) }}
            onDoubleClick={(e) => { e.stopPropagation(); onNodeDoubleClick(n.id) }}
          >
            {isLeaf ? (
              <>
                <circle cx={n.x} cy={n.y} r={isSelected ? 5 : 3}
                  fill="#00F5D4"
                  opacity={dim ? 0.12 : isSelected ? 1 : 0.8}
                  stroke={isSelected ? '#fff' : 'none'}
                  strokeWidth={isSelected ? 1.5 : 0} />
                <text
                  x={labelX} y={labelY + 4}
                  fontSize={10}
                  fill={bright ? '#00F5D4' : '#94a3b8'}
                  opacity={dim ? 0.12 : 1}
                  fontFamily="'JetBrains Mono', monospace"
                  fontWeight={isSelected ? 'bold' : 'normal'}
                  textAnchor={flip ? 'end' : 'start'}
                  transform={`rotate(${-(deg - (flip ? 180 : 0))}, ${labelX}, ${labelY})`}
                >
                  {n.name}
                </text>
                <title>{n.name}{blTip ? ` · ${blTip}` : ''}</title>
              </>
            ) : (
              <>
                <circle cx={n.x} cy={n.y} r={isSelected ? 7 : 5}
                  fill={dim ? '#1e293b' : isSelected ? '#00F5D4' : '#1e293b'}
                  stroke={isSelected ? '#fff' : bright ? '#00F5D4' : '#475569'}
                  strokeWidth={isSelected ? 2 : bright ? 2 : 1.5}
                  opacity={dim ? 0.12 : 0.85} />
                {n.bootstrap !== null && n.bootstrap >= 50 && (
                  <text x={n.x} y={n.y - 7} fontSize={8}
                    fill={bootstrapColour(n.bootstrap)} textAnchor="middle" fontWeight="bold"
                    opacity={dim ? 0.12 : 1}>
                    {Math.round(n.bootstrap)}
                  </text>
                )}
                <text x={n.x} y={n.y + 4} fontSize={6}
                  fill={bright ? '#00F5D4' : '#64748b'}
                  opacity={dim ? 0.12 : 0.7}
                  textAnchor="middle" fontFamily="sans-serif">
                  {n.name || `N${i}`}
                </text>
                <title>Node {n.name || `N${i}`}{blTip ? ` · ${blTip}` : ''}{n.bootstrap !== null ? ` · bootstrap: ${n.bootstrap}` : ''}</title>
              </>
            )}
          </g>
        )
      })}
    </>
  )
}

// ─── Node info panel ──────────────────────────────────────────────────────────

function NodeInfoPanel({ node, allNodes }: { node: TreeNode; allNodes: TreeNode[] }) {
  const isLeaf = node.children.length === 0
  const leavesInSubtree = isLeaf ? 1 : countLeaves(node)
  const depth = (() => {
    let d = 0; let cur: TreeNode | null = node.parent
    while (cur) { d++; cur = cur.parent }
    return d
  })()
  const leafName = isLeaf ? (node.name || '').split('|').pop()?.split('_')[0] || node.name : ''
  const isValidAccession = leafName.length >= 4 && /^[A-Z0-9_]+$/.test(leafName)

  return (
    <div className="glass-card p-4 space-y-2 text-sm">
      <div className="flex items-center justify-between">
        <span className="text-text-primary font-medium">
          {isLeaf ? node.name || 'Leaf' : 'Internal Node'}
        </span>
        <span className="text-text-secondary text-xs">
          {isLeaf ? 'leaf' : 'hub'} · depth {depth}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-text-secondary mr-1">Branch length:</span>
          <span className="text-accent-cyan font-mono">{node.length.toFixed(5)}</span>
        </div>
        {node.bootstrap !== null && (
          <div>
            <span className="text-text-secondary mr-1">Bootstrap:</span>
            <span className="font-mono" style={{ color: bootstrapColour(node.bootstrap) }}>
              {node.bootstrap}
            </span>
          </div>
        )}
        {!isLeaf && (
          <div>
            <span className="text-text-secondary mr-1">Subtree leaves:</span>
            <span className="text-text-primary font-mono">{leavesInSubtree}</span>
          </div>
        )}
        <div>
          <span className="text-text-secondary mr-1">Node ID:</span>
          <span className="text-text-primary font-mono">{node.id}</span>
        </div>
      </div>
      {isLeaf && isValidAccession && (
        <div className="pt-2 border-t border-glass-border flex items-center justify-end gap-2">
          <a href={`https://www.ncbi.nlm.nih.gov/protein/${leafName}`} target="_blank" rel="noreferrer"
            className="text-xs text-accent-cyan hover:underline">View on NCBI</a>
          <button onClick={() => window.open(`/analyze/blast?sequence=${leafName}`, '_blank')}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-accent-cyan/10 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/20 transition">
            <Search className="w-3 h-3" /> BLAST ortholog (F6)
          </button>
        </div>
      )}
    </div>
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
  const [hoveredId, setHoveredId]   = useState<number | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [collapsedIds, setCollapsedIds] = useState<Set<number>>(new Set())

  // zoom / pan
  const [transform, setTransform] = useState({ scale: 1, x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef({ startX: 0, startY: 0, startS: 1, startTx: 0, startTy: 0, moved: false })
  const svgRef = useRef<SVGSVGElement>(null)

  const treeData = useMemo(() => {
    try {
      const root = parseNewick(newick)
      if (layout === 'rectangular') {
        return { ...buildRectangularLayout(root, collapsedIds), error: null as string | null }
      } else {
        return { ...buildCircularLayout(root, collapsedIds), error: null as string | null }
      }
    } catch (e) {
      return { nodes: [], height: 400, maxDepth: 0, rootNode: null as TreeNode | null, error: String(e) }
    }
  }, [newick, layout, collapsedIds])

  const pathSet = useMemo(() => computePathSet(treeData.nodes, hoveredId), [hoveredId, treeData.nodes])

  const selectedNode = useMemo(() => {
    if (selectedId === null) return null
    return findNodeById(treeData.nodes, selectedId)
  }, [selectedId, treeData.nodes])

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

  // ── Zoom / pan event handlers ──────────────────────────────────────────────

  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault()
    const svg = svgRef.current
    if (!svg) return
    const rect = svg.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top

    const delta = e.deltaY > 0 ? 0.88 : 1 / 0.88
    const newScale = clamp(transform.scale * delta, 0.08, 12)
    const ratio = newScale / transform.scale
    setTransform({
      scale: newScale,
      x: mx - (mx - transform.x) * ratio,
      y: my - (my - transform.y) * ratio,
    })
  }, [transform])

  // Attach non-passive wheel listener so e.preventDefault() blocks page scroll
  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    el.addEventListener('wheel', handleWheel, { passive: false })
    return () => el.removeEventListener('wheel', handleWheel)
  }, [handleWheel])

  const resetView = useCallback(() => {
    setTransform({ scale: 1, x: 0, y: 0 })
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (e.button !== 0) return
    setIsDragging(true)
    dragRef.current = {
      startX: e.clientX, startY: e.clientY,
      startS: transform.scale, startTx: transform.x, startTy: transform.y,
      moved: false,
    }
  }, [transform])

  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDragging) return
    const drag = dragRef.current
    const dx = e.clientX - drag.startX
    const dy = e.clientY - drag.startY
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) drag.moved = true
    setTransform(t => ({ ...t, x: drag.startTx + dx, y: drag.startTy + dy }))
  }, [isDragging])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  // ── Node interaction handlers ───────────────────────────────────────────────

  const handleNodeHover = useCallback((id: number | null) => {
    setHoveredId(id)
  }, [])

  const handleNodeClick = useCallback((id: number) => {
    setIsDragging(false)
    if (dragRef.current.moved) return
    setSelectedId(prev => prev === id ? null : id)
  }, [])

  const handleNodeDoubleClick = useCallback((id: number) => {
    setCollapsedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
    setSelectedId(null)
  }, [])

  const handleSvgClick = useCallback(() => {
    setSelectedId(null)
    setHoveredId(null)
  }, [])

  const expandAll = useCallback(() => setCollapsedIds(new Set()), [])
  const collapseAllInternal = useCallback(() => {
    setCollapsedIds(new Set(treeData.nodes.filter(n => n.children.length > 0).map(n => n.id)))
  }, [treeData.nodes])

  // ── Error state ─────────────────────────────────────────────────────────────

  if (treeData.error) {
    return (
      <div className="glass-card p-6 text-red-400">
        <p className="font-medium mb-1">Failed to parse Newick string</p>
        <pre className="text-xs opacity-70 overflow-auto">{treeData.error}</pre>
        <pre className="text-xs opacity-40 mt-2 overflow-auto">{newick.slice(0, 200)}</pre>
      </div>
    )
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">

      {/* Toolbar */}
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

        <button onClick={resetView}
          className="text-xs px-3 py-1.5 rounded-lg border border-glass-border
            text-text-secondary hover:text-text-primary hover:border-accent-cyan/40 transition-colors">
          ↺ Fit
        </button>

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
                text-text-secondary hover:text-text-primary hover:border-accent-cyan/40 transition-colors">
              ↓ {label}
            </button>
          ))}
        </div>
      </div>

      {/* Collapse controls */}
      <div className="flex gap-2 text-[11px]">
        <button onClick={expandAll}
          className="px-2.5 py-1 rounded border border-glass-border text-text-secondary hover:text-text-primary transition-colors">
          Expand all
        </button>
        <button onClick={collapseAllInternal}
          className="px-2.5 py-1 rounded border border-glass-border text-text-secondary hover:text-text-primary transition-colors">
          Collapse all
        </button>
        <span className="text-text-secondary self-center opacity-60">
          {hoveredId !== null ? 'Hover: path highlighted · ' : ''}
          Double-click internal node to collapse/expand
        </span>
      </div>

      {/* SVG */}
      <div className="bg-surface-1 rounded-xl border border-glass-border overflow-hidden select-none"
        style={{ maxHeight: '75vh' }}>
        <svg
          ref={svgRef}
          viewBox={layout === 'rectangular'
            ? `0 0 ${SVG_W} ${treeData.height}`
            : `0 0 ${CIRC_SIZE} ${CIRC_SIZE}`}
          width="100%"
          style={{ maxHeight: '70vh', background: '#04040A', cursor: isDragging ? 'grabbing' : 'grab' }}
          xmlns="http://www.w3.org/2000/svg"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onClick={handleSvgClick}
        >
          <rect width="100%" height="100%" fill="#04040A" />

          <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
            {layout === 'rectangular' ? (
              <RectangularTree
                nodes={treeData.nodes}
                svgH={treeData.height}
                maxDepth={treeData.maxDepth}
                pathSet={pathSet}
                selectedId={selectedId}
                hoveredId={hoveredId}
                onNodeHover={handleNodeHover}
                onNodeClick={handleNodeClick}
                onNodeDoubleClick={handleNodeDoubleClick}
              />
            ) : (
              <CircularTree
                nodes={treeData.nodes}
                pathSet={pathSet}
                selectedId={selectedId}
                hoveredId={hoveredId}
                onNodeHover={handleNodeHover}
                onNodeClick={handleNodeClick}
                onNodeDoubleClick={handleNodeDoubleClick}
              />
            )}
          </g>
        </svg>
      </div>

      <p className="text-text-secondary text-xs">
        {treeData.nodes.filter(n => n.children.length === 0).length} taxa ·{' '}
        {sequenceType === 'protein' ? 'protein' : 'nucleotide'} sequences
      </p>

      {/* Selected node info panel */}
      {selectedNode && (
        <NodeInfoPanel node={selectedNode} allNodes={treeData.nodes} />
      )}

      {alignment && (
        <div className="border border-glass-border rounded-xl overflow-hidden">
          <button
            onClick={() => setShowAln(v => !v)}
            className="w-full flex items-center justify-between px-4 py-3
              text-text-secondary hover:text-text-primary transition-colors text-sm">
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
            text-text-secondary hover:text-text-primary transition-colors text-sm">
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

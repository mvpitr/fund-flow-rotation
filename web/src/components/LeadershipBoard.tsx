import type { Payload } from '../types'
import { fmtDollars, fmtSigma } from '../format'

interface Row {
  name: string
  ticker: string
  rs: number
  ghost: number | null
  cf: number | null
}

const X0 = 240   // chart area, left
const X1 = 688   // chart area, right
const RS_X = 782 // right edge of the RS column
const CF_X = 950 // right edge of the dollar column
const HEADER_H = 30
const ROW_H = 34

/**
 * Ranked board: signed RS bar now (RS = relative strength, the sector's flow vs
 * the whole market in sigma units), hollow marker `lag` months ago, trailing
 * dollar flow on the right.
 */
export function LeadershipBoard({ data }: { data: Payload }) {
  const last = data.months.length - 1
  const ghostIdx = last - data.lag
  const rows: Row[] = data.sectors
    .filter(s => s.rs[last] != null)
    .map(s => ({
      name: s.name,
      ticker: s.ticker,
      rs: s.rs[last] as number,
      ghost: ghostIdx >= 0 ? s.rs[ghostIdx] : null,
      cf: s.cf[last],
    }))

  const maxAbs = Math.max(...rows.flatMap(r => [Math.abs(r.rs), Math.abs(r.ghost ?? 0)]))
  const lim = Math.max(1, Math.ceil(2 * maxAbs) / 2)
  const x = (v: number) => X0 + ((v + lim) / (2 * lim)) * (X1 - X0)
  const H = HEADER_H + rows.length * ROW_H + 10

  const ticks: number[] = []
  for (let t = -Math.floor(lim); t <= Math.floor(lim); t++) ticks.push(t)

  return (
    <svg viewBox={`0 0 960 ${H}`} width="100%" role="img"
         aria-label="Sector flow leadership board">
      {ticks.map(t => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={HEADER_H - 6} y2={H - 8}
                stroke={t === 0 ? 'var(--muted)' : 'var(--line)'}
                strokeOpacity={t === 0 ? 0.8 : 1} />
          <text x={x(t)} y={HEADER_H - 12} textAnchor="middle" fontSize={10}
                fill="var(--muted)" className="mono">
            {t === 0 ? '0' : `${t > 0 ? '+' : ''}${t}σ`}
          </text>
        </g>
      ))}
      <text x={RS_X} y={HEADER_H - 12} textAnchor="end" fontSize={10}
            fill="var(--muted)" className="mono">RS now</text>
      <text x={CF_X} y={HEADER_H - 12} textAnchor="end" fontSize={10}
            fill="var(--muted)" className="mono">net flow, {data.window}m</text>

      {rows.map((r, i) => {
        const cy = HEADER_H + i * ROW_H + ROW_H / 2
        const col = r.rs >= 0 ? 'var(--pos)' : 'var(--neg)'
        const bx = Math.min(x(0), x(r.rs))
        const bw = Math.abs(x(r.rs) - x(0))
        return (
          <g key={r.ticker}>
            <title>
              {`${r.name} (${r.ticker}): RS ${fmtSigma(r.rs)}σ now` +
                (r.ghost != null ? `, ${fmtSigma(r.ghost)}σ three months ago` : '') +
                (r.cf != null ? `; ${data.window}-month net flow ${fmtDollars(r.cf)}` : '')}
            </title>
            <text x={2} y={cy + 4} fontSize={13} fill="var(--accent)"
                  className="mono">{r.ticker}</text>
            <text x={64} y={cy + 4} fontSize={13} fill="var(--ink)"
                  opacity={0.92}>{r.name}</text>
            {r.ghost != null && (
              <line x1={x(r.ghost)} x2={x(r.rs)} y1={cy} y2={cy}
                    stroke="var(--muted)" strokeWidth={1}
                    strokeDasharray="2 3" opacity={0.8} />
            )}
            <rect x={bx} y={cy - 5} width={bw} height={10} rx={2}
                  fill={col} fillOpacity={0.9} />
            {r.ghost != null && (
              <circle cx={x(r.ghost)} cy={cy} r={4} fill="var(--panel)"
                      stroke="var(--muted)" strokeWidth={1.4} />
            )}
            <text x={RS_X} y={cy + 4} textAnchor="end" fontSize={12.5}
                  fill={col} className="num">{fmtSigma(r.rs)}σ</text>
            {r.cf != null && (
              <text x={CF_X} y={cy + 4} textAnchor="end" fontSize={12.5}
                    fill={r.cf >= 0 ? 'var(--pos)' : 'var(--neg)'}
                    className="num">{fmtDollars(r.cf)}</text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

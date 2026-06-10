const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** '2026-03-31' -> 'Mar 2026' (no Date parsing: avoids timezone shifts). */
export function fmtMonth(iso: string): string {
  const [y, m] = iso.split('-')
  return `${MONTHS[Number(m) - 1]} ${y}`
}

/** Signed sigma value: 1.824 -> '+1.82' */
export function fmtSigma(v: number): string {
  return `${v >= 0 ? '+' : '-'}${Math.abs(v).toFixed(2)}`
}

/** Signed compact dollars: 3.42e9 -> '+$3.4B' */
export function fmtDollars(v: number): string {
  const sign = v < 0 ? '-' : '+'
  const a = Math.abs(v)
  if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(1)}B`
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(0)}M`
  return `${sign}$${(a / 1e3).toFixed(0)}K`
}

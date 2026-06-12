import rawData from './data.json'
import type { Payload } from './types'
import { LeadershipBoard } from './components/LeadershipBoard'
import { RotationStrip } from './components/RotationStrip'
import { TurnoverStrip } from './components/TurnoverStrip'
import { fmtMonth } from './format'

const data = rawData as unknown as Payload

export default function App() {
  return (
    <main>
      <header className="masthead">
        <div>
          <h1>Fund-Flow Rotation Map</h1>
          <p className="tagline">
            Where investor capital is actually moving across the eleven US equity
            sectors: monthly net fund flows reconstructed from SEC N-PORT filings,
            stripped of price moves.
          </p>
        </div>
        <span className="asof">as of {fmtMonth(data.as_of)} · provisional</span>
      </header>

      <section className="card">
        <h2>Flow leadership</h2>
        <p className="sub">
          Bar = current relative flow strength (RS, in σ against the sector's own
          12-month norm). The hollow marker is the same reading three months ago,
          so the gap between marker and bar tip is the trend. Right column:
          trailing {data.window}-month net dollar flow.
        </p>
        <LeadershipBoard data={data} />
      </section>

      <section className="card">
        <h2>Five years of rotation</h2>
        <p className="sub">
          The same measure, every month since the panel starts: teal = gaining
          share of flow, coral = losing it, near-background = no clear signal.
          Rows keep the leadership order above. Hover any cell for exact values;
          the last month is provisional.
        </p>
        <RotationStrip data={data} />
      </section>

      <section className="card">
        <h2>Rotation intensity</h2>
        <p className="sub">
          Dollars that changed sectors each month. Each sector&apos;s flow, less its
          pro-rata share of the market-wide tide, nets to zero across sectors; the
          matched size of the winning and losing sides is the money actually
          rotating. Taller bars mean a more violent rotation, whoever wins it.
        </p>
        <TurnoverStrip data={data} />
      </section>

      <footer>
        Built from public SEC data; flows are reported by the funds, not estimated.
        Methodology and source:{' '}
        <a href="https://github.com/mvpitr/fund-flow-rotation">
          github.com/mvpitr/fund-flow-rotation
        </a>
      </footer>
    </main>
  )
}

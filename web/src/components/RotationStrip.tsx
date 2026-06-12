import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { Payload } from '../types'
import { C, MONO } from '../theme'
import { fmtDollars, fmtMonth, fmtSigma } from '../format'

echarts.use([HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, CanvasRenderer])

/**
 * Sector x month strip of RS (relative strength: the sector's flow vs the whole
 * market, standardized to sigma units): teal gaining, coral losing, background =
 * no signal.
 */
export function RotationStrip({ data }: { data: Payload }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const chart = echarts.init(el)
    const names = data.sectors.map(s => s.name)   // strongest first (board order)
    const lastIdx = data.months.length - 1
    const points: [number, number, number][] = []
    data.sectors.forEach((s, si) => {
      s.rs.forEach((v, mi) => {
        if (v != null) points.push([mi, names.length - 1 - si, v])  // y 0 = bottom
      })
    })

    chart.setOption({
      grid: { left: 168, right: 12, top: 10, bottom: 64 },
      xAxis: {
        type: 'category',
        data: data.months,
        axisLine: { lineStyle: { color: C.line } },
        axisTick: { show: false },
        axisLabel: {
          color: C.muted, fontFamily: MONO, fontSize: 10,
          interval: (i: number) => data.months[i].slice(5, 7) === '01',
          formatter: (iso: string) => iso.slice(0, 4),
        },
      },
      yAxis: {
        type: 'category',
        data: [...names].reverse(),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: C.ink, fontSize: 12.5 },
      },
      visualMap: {
        min: -2.5, max: 2.5, calculable: false,
        orient: 'horizontal', right: 8, bottom: 8,
        itemWidth: 9, itemHeight: 110,
        text: ['gaining', 'losing'],
        textStyle: { color: C.muted, fontFamily: MONO, fontSize: 10 },
        // Flat middle band: weak months sit at background, episodes carry colour.
        inRange: { color: [C.neg, '#141a23', '#141a23', C.pos] },
      },
      tooltip: {
        backgroundColor: C.panel,
        borderColor: C.line,
        textStyle: { color: C.ink, fontFamily: MONO, fontSize: 11 },
        formatter: (p: { data: [number, number, number] }) => {
          const [mi, yi, v] = p.data
          const s = data.sectors[names.length - 1 - yi]
          const f = s.flow[mi]
          const prov = mi === lastIdx ? ' (provisional)' : ''
          return `${s.ticker} ${s.name}<br/>${fmtMonth(data.months[mi])}${prov}<br/>` +
                 `RS ${fmtSigma(v)}σ` +
                 (f != null ? ` · month flow ${fmtDollars(f)}` : '')
        },
      },
      series: [{
        type: 'heatmap',
        data: points,
        itemStyle: { borderColor: C.panel, borderWidth: 1 },
        emphasis: { itemStyle: { borderColor: C.accent, borderWidth: 1 } },
      }],
    })

    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
    }
  }, [data])

  return <div ref={ref} style={{ height: 430 }} />
}

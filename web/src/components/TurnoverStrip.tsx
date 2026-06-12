import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { Payload } from '../types'
import { C, MONO } from '../theme'
import { fmtMonth } from '../format'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

/** Monthly gross rotation turnover: the dollars that changed sectors. */
export function TurnoverStrip({ data }: { data: Payload }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const chart = echarts.init(el)
    const { months, T, tau } = data.turnover
    const lastIdx = months.length - 1

    chart.setOption({
      grid: { left: 56, right: 12, top: 12, bottom: 28 },
      xAxis: {
        type: 'category',
        data: months,
        axisLine: { lineStyle: { color: C.line } },
        axisTick: { show: false },
        axisLabel: {
          color: C.muted, fontFamily: MONO, fontSize: 10,
          interval: (i: number) => months[i].slice(5, 7) === '01',
          formatter: (iso: string) => iso.slice(0, 4),
        },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: C.line } },
        axisLabel: {
          color: C.muted, fontFamily: MONO, fontSize: 10,
          formatter: (v: number) => (v === 0 ? '0' : `$${v / 1e9}B`),
        },
      },
      tooltip: {
        backgroundColor: C.panel,
        borderColor: C.line,
        textStyle: { color: C.ink, fontFamily: MONO, fontSize: 11 },
        formatter: (p: { dataIndex: number }) => {
          const i = p.dataIndex
          const prov = i === lastIdx ? ' (provisional)' : ''
          return `${fmtMonth(months[i])}${prov}<br/>` +
                 `rotated $${(T[i] / 1e9).toFixed(2)}B · ` +
                 `${(tau[i] * 100).toFixed(2)}% of assets`
        },
      },
      series: [{
        type: 'bar',
        data: T,
        barCategoryGap: '25%',
        itemStyle: { color: C.accent, opacity: 0.85 },
        emphasis: { itemStyle: { opacity: 1 } },
      }],
    })

    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
    }
  }, [data])

  return <div ref={ref} style={{ height: 240 }} />
}

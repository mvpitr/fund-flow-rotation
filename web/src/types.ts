export interface SectorSeries {
  name: string
  ticker: string
  rs: (number | null)[]
  cf: (number | null)[]
  flow: (number | null)[]
}

export interface TurnoverBlock {
  months: string[]
  T: number[]
  tau: number[]
}

export interface Payload {
  as_of: string
  provisional: boolean
  window: number
  lag: number
  months: string[]
  sectors: SectorSeries[]
  turnover: TurnoverBlock
}

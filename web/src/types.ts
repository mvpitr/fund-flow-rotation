export interface SectorSeries {
  name: string
  ticker: string
  rs: (number | null)[]
  cf: (number | null)[]
  flow: (number | null)[]
}

export interface Payload {
  as_of: string
  provisional: boolean
  window: number
  lag: number
  months: string[]
  sectors: SectorSeries[]
}

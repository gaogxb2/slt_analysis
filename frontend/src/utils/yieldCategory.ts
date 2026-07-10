import type { MaterialMember } from '../api'

/** 与 slt_yield/yield_analyzer.py 保持一致 */
export const TEMP_LABELS = ['常温', '低温', '高温'] as const
export type TempLabel = (typeof TEMP_LABELS)[number]

export const CATEGORY_COLORS: Record<TempLabel, string> = {
  常温: '#4472C4',
  低温: '#70AD47',
  高温: '#ED7D31',
}

export const TOTAL_YIELD_COLOR = '#C00000'

export const DEFAULT_CATEGORY_MAP: Record<string, TempLabel> = {
  MT1: '常温',
  MT2: '常温',
  MT3: '常温',
  MT9: '低温',
  MT10: '高温',
  MT11: '高温',
}

export interface ProcessYieldRow {
  process: string
  passQty: number
  testQty: number
  yield: number
  tempType: TempLabel
  lotNo: string
  roundKey: string
}

const STORAGE_KEY = 'slt_mt_temperature_categories'

export function sortProcesses(processes: string[]): string[] {
  return [...processes].sort((a, b) => {
    const digits = (name: string) => {
      const d = name.replace(/\D/g, '')
      return d ? parseInt(d, 10) : 0
    }
    const prefix = (name: string) => (name.length >= 2 ? name.slice(0, 2) : name)
    return prefix(a).localeCompare(prefix(b)) || digits(a) - digits(b) || a.localeCompare(b)
  })
}

/** 从 SUM 入库数据提取各 MT 初轮良率（对应 slt_yield 工序维度） */
export function membersToProcessRows(members: MaterialMember[]): ProcessYieldRow[] {
  const rows: ProcessYieldRow[] = []
  for (const m of members) {
    const first = m.rounds[0]
    if (!first) continue
    rows.push({
      process: m.stage,
      passQty: first.pass_count,
      testQty: first.input_qty,
      yield: first.yield_pct / 100,
      tempType: '常温',
      lotNo: m.lot_no,
      roundKey: first.round_key,
    })
  }
  return rows.sort((a, b) => sortProcesses([a.process, b.process]).indexOf(a.process)
    - sortProcesses([a.process, b.process]).indexOf(b.process))
}

export function applyCategoryMap(
  rows: ProcessYieldRow[],
  categoryMap: Record<string, TempLabel>,
): ProcessYieldRow[] {
  return rows.map((r) => ({
    ...r,
    tempType: categoryMap[r.process] ?? DEFAULT_CATEGORY_MAP[r.process] ?? '常温',
  }))
}

/** slt_yield: calc_category_yield */
export function calcCategoryYield(rows: ProcessYieldRow[], category: TempLabel): number | null {
  const catRows = rows.filter((r) => r.tempType === category)
  if (!catRows.length) return null
  const testQty = catRows.reduce((s, r) => s + r.testQty, 0)
  if (testQty === 0) return null
  const passQty = catRows.reduce((s, r) => s + r.passQty, 0)
  return passQty / testQty
}

/** slt_yield: calc_total_yield — 常温 × 低温 × 高温 */
export function calcTotalYield(rows: ProcessYieldRow[]): number | null {
  let total = 1
  for (const cat of TEMP_LABELS) {
    const y = calcCategoryYield(rows, cat)
    if (y === null) return null
    total *= y
  }
  return total
}

export function getTestQtyByCategory(rows: ProcessYieldRow[]): Record<TempLabel, number> {
  const result: Record<TempLabel, number> = { 常温: 0, 低温: 0, 高温: 0 }
  for (const cat of TEMP_LABELS) {
    result[cat] = rows.filter((r) => r.tempType === cat).reduce((s, r) => s + r.testQty, 0)
  }
  return result
}

export function loadCategoryMap(materialKey: string, stages: string[]): Record<string, TempLabel> {
  let stored: Record<string, Record<string, TempLabel>> = {}
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) stored = JSON.parse(raw)
  } catch {
    /* ignore */
  }
  const saved = stored[materialKey] ?? {}
  const map: Record<string, TempLabel> = {}
  for (const stage of stages) {
    map[stage] = saved[stage] ?? DEFAULT_CATEGORY_MAP[stage] ?? '常温'
  }
  return map
}

export function saveCategoryMap(materialKey: string, map: Record<string, TempLabel>): void {
  let stored: Record<string, Record<string, TempLabel>> = {}
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) stored = JSON.parse(raw)
  } catch {
    /* ignore */
  }
  stored[materialKey] = map
  localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
}

export function validateCategories(map: Record<string, TempLabel>): string | null {
  const used = new Set(Object.values(map))
  for (const cat of TEMP_LABELS) {
    if (!used.has(cat)) {
      return `请为至少一个 MT 选择「${cat}」`
    }
  }
  return null
}

export function fmtPct(value: number | null, digits = 1): string {
  if (value === null) return '-'
  return `${(value * 100).toFixed(digits)}%`
}

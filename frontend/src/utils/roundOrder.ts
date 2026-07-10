/** MT1 -> 0, M2 -> 0, M2R1 -> 1, M2R2 -> 2 */
export function parseRoundOrder(roundKey: string): [number, number] {
  const m = roundKey.match(/R(\d+)$/)
  if (m) return [1, parseInt(m[1], 10)]
  return [0, 0]
}

export function stageOrder(stage: string): number {
  const m = stage.match(/MT(\d+)/i)
  return m ? parseInt(m[1], 10) : 0
}

export function sortDieRecords<T extends { stage?: string; round_key?: string; lot_no?: string }>(
  rows: T[],
): T[] {
  return [...rows].sort((a, b) => {
    const sa = stageOrder(a.stage || '')
    const sb = stageOrder(b.stage || '')
    if (sa !== sb) return sa - sb
    const [ta, na] = parseRoundOrder(a.round_key || '')
    const [tb, nb] = parseRoundOrder(b.round_key || '')
    if (ta !== tb) return ta - tb
    if (na !== nb) return na - nb
    return (a.lot_no || '').localeCompare(b.lot_no || '')
  })
}

export function dieFinalStatus(rows: { boot_on?: string; error_code?: number }[]): string {
  if (!rows.length) return '未知'
  const last = rows[rows.length - 1]
  if (last.error_code !== undefined && last.error_code !== null) {
    return String(last.error_code).startsWith('10') ? 'PASS' : 'FAIL'
  }
  return (last.boot_on || '').toUpperCase() === 'PASS' ? 'PASS' : 'FAIL'
}

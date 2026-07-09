const SUFFIX_RE = /^(A[A-E]\d)$/

export function materialKey(lotNo: string): string {
  const s = (lotNo || '').trim()
  if (s.length >= 3 && SUFFIX_RE.test(s.slice(-3))) {
    return s.slice(0, -3)
  }
  return s
}

export function materialLabel(key: string): string {
  return key ? `${key}*` : key
}

export function lotDetailPath(lotNo: string, stage?: string): string {
  const q = stage ? `?stage=${encodeURIComponent(stage)}` : ''
  return `/lots/${encodeURIComponent(lotNo)}${q}`
}

export function materialPath(key: string): string {
  return `/material/${encodeURIComponent(key)}`
}

export function chipPath(dieId: string): string {
  return `/chips/${encodeURIComponent(dieId.replace(/\s+/g, ' ').trim())}`
}

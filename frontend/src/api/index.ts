import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface FailBreakdown {
  code: number
  description: string
  count: number
  sw_category?: number
  hw_bin?: number
}

export interface LotSummary {
  id: number
  lot_no: string
  stage: string
  bin: number
  traveler_qty: number
  lot_start_date?: string
  temperature?: number
  input_qty: number
  final_pass: number
  final_fail: number
  final_yield_pct: number
  last_report_date?: string
  round_count: number
  final_fail_breakdown: FailBreakdown[]
  initial_fail_breakdown: FailBreakdown[]
}

export interface BinSummary {
  sw_category: number
  hw_bin: number
  code: number
  description: string
  count: number
  percent: number
}

export interface SiteCounter {
  site_no: number
  counter: number
  pass_count: number
  fail_count: number
  yield_pct: number
}

export interface TestRound {
  id: number
  round_key: string
  input_qty: number
  pass_count: number
  fail_count: number
  yield_pct: number
  start_time?: string
  report_date?: string
  sub_file_count: number
  log_count?: number
  matched_count?: number
  bin_summaries: BinSummary[]
  site_counters: SiteCounter[]
}

export interface ValidationIssue {
  level: string
  code: string
  message: string
  round_key?: string
}

export interface LotDetail {
  id: number
  lot_no: string
  stage: string
  bin: number
  traveler_qty: number
  lot_start_date?: string
  temperature?: number
  final_stats: { input_qty: number; final_pass: number; final_fail: number; yield_pct: number }
  rounds: TestRound[]
  sum_files: Array<{
    filename: string
    test_mode: string
    round_key: string
    sub_batch: number
    input_qty: number
    pass_count: number
    fail_count: number
    yield_pct: number
  }>
  validation_issues: ValidationIssue[]
}

export interface DieRecord {
  id?: number
  die_id: string
  barcode?: string
  lot_no: string
  stage: string
  round_key: string
  test_mode?: string
  site: number
  error_code: number
  software_bin: number
  boot_on: string
  tj?: string
  bios_time?: string
  test_time?: string
  temperature?: number
  log_status?: string
  chip_log_id?: number
}

export interface RoundDie {
  id: number
  die_id: string
  barcode?: string
  site: number
  boot_on: string
  error_code: number
  software_bin: number
  test_mode?: string
  log_status: string
  chip_log_id?: number
}

export interface ReconcileSummary {
  sum_count: number
  log_count: number
  matched_count: number
  sum_only_count: number
  log_only_count: number
  mismatch_count: number
}

export interface ReconcileRow {
  status: string
  die_record_id?: number
  chip_log_id?: number
  die_id: string
  test_mode: string
  round_key: string
  site: number
  barcode: string
  sum_boot_on: string
  log_pf: string
  sum_bin: number
  log_bin: number
  diff_summary: string
}

export interface ReconcileResult {
  lot_no: string
  stage: string
  summary: ReconcileSummary
  rows: ReconcileRow[]
}

export interface OneTestRow {
  test_txt: string
  pattern: string
  result: string
  pf: string
  test_time_ms: number
}

export interface ChipLogDieId {
  die_id_str: string
  die_id_name: string
  lot: string
  wafer: string
  x: string
  y: string
  ordinal: number
}

export interface ChipLogDetail {
  id: number
  lot_no: string
  stage: string
  test_mode: string
  round_key: string
  site: number
  primary_die_id: string
  barcode: string
  pf: string
  soft_bin: number
  test_time: string
  test_start: string
  file_path: string
  die_record_id?: number
  onetests: OneTestRow[]
  die_ids: ChipLogDieId[]
  sum_compare?: {
    boot_on: string
    software_bin: number
    site: number
    test_mode: string
    test_time: string
  }
  header: Record<string, string>
}

export interface MaterialGroupSummary {
  material_key: string
  material_label: string
  member_count: number
  lot_nos: string[]
  stages: string[]
}

export interface MaterialGroup {
  material_key: string
  material_label: string
  member_count: number
  members: MaterialMember[]
  round_rows: MaterialRoundRow[]
}

export interface MaterialMember {
  lot_no: string
  stage: string
  input_qty: number
  final_pass: number
  final_fail: number
  final_yield_pct: number
  round_count: number
  rounds: MaterialRound[]
  final_fail_breakdown: FailBreakdown[]
}

export interface MaterialRound {
  round_key: string
  input_qty: number
  pass_count: number
  fail_count: number
  yield_pct: number
  fail_bins: FailBreakdown[]
}

export interface MaterialRoundRow {
  lot_no: string
  stage: string
  round_key: string
  label: string
  input_qty: number
  pass_count: number
  fail_count: number
  yield_pct: number
  fail_bins: FailBreakdown[]
}

export interface Overview {
  lot_count: number
  total_input: number
  total_final_pass: number
  avg_yield_pct: number
  final_fail_breakdown: FailBreakdown[]
  lots: LotSummary[]
}

export const getMaterialCatalog = (params?: { search?: string }) =>
  api.get<MaterialGroupSummary[]>('/material-groups/catalog', { params }).then((r) => r.data)
export const getMaterialGroups = (params?: {
  lot_no?: string
  stage?: string
  material_keys?: string
}) =>
  api.get<MaterialGroup[]>('/material-groups', { params }).then((r) => r.data)
export const getOverview = (params?: { lot_no?: string; stage?: string }) =>
  api.get<Overview>('/stats/overview', { params }).then((r) => r.data)
export const getLots = (params?: { lot_no?: string; stage?: string }) =>
  api.get<LotSummary[]>('/lots', { params }).then((r) => r.data)
export const getLot = (lotNo: string, stage?: string) =>
  api.get<LotDetail>(`/lots/${encodeURIComponent(lotNo)}`, { params: { stage } }).then((r) => r.data)
export const getRoundDies = (
  lotNo: string,
  roundKey: string,
  params?: { only_fail?: boolean; stage?: string },
) =>
  api
    .get<RoundDie[]>(`/lots/${encodeURIComponent(lotNo)}/rounds/${encodeURIComponent(roundKey)}/dies`, { params })
    .then((r) => r.data)
export const getReconcile = (
  lotNo: string,
  params?: {
    stage?: string
    test_mode?: string
    round_key?: string
    only_fail?: boolean
    only_abnormal?: boolean
  },
) =>
  api.get<ReconcileResult>(`/lots/${encodeURIComponent(lotNo)}/reconcile`, { params }).then((r) => r.data)
export const getChipLog = (id: number) => api.get<ChipLogDetail>(`/chip-logs/${id}`).then((r) => r.data)
export const getDieLog = (dieRecordId: number) =>
  api.get<ChipLogDetail>(`/dies/${dieRecordId}/log`).then((r) => r.data)
export const searchDies = (params: { die_id?: string; barcode?: string }) =>
  api.get<DieRecord[]>('/dies/search', { params }).then((r) => r.data)
export const uploadFiles = (files: File[]) => {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  return api.post('/import/upload', fd).then((r) => r.data)
}
export const scanTestdata = (path?: string) =>
  api.post('/import/scan', null, { params: { path } }).then((r) => r.data)
export const scanTestlogs = (path?: string) =>
  api.post('/import/scan-logs', null, { params: { path } }).then((r) => r.data)
export const getImportLogs = () => api.get('/import/status').then((r) => r.data)

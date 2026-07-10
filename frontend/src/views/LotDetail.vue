<template>
  <div v-loading="loading">
    <el-breadcrumb separator="/" style="margin-bottom: 12px">
      <el-breadcrumb-item :to="{ path: '/material' }">物料批次</el-breadcrumb-item>
      <el-breadcrumb-item
        v-if="materialGroupKey"
        :to="{ path: `/material/${encodeURIComponent(materialGroupKey)}` }"
      >{{ materialGroupLabel }}</el-breadcrumb-item>
      <el-breadcrumb-item>{{ lotNo }} / {{ lot?.stage }}</el-breadcrumb-item>
    </el-breadcrumb>

    <div class="page-header">
      <h2 class="page-title" style="margin: 0">批次详情 — {{ lotNo }}</h2>
      <el-button type="primary" @click="$router.push(`/lots/${lotNo}/reconcile`)">SUM/Log 对账</el-button>
    </div>

    <template v-if="lot">
      <el-descriptions :column="4" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="LOT NO.">{{ lot.lot_no }}</el-descriptions-item>
        <el-descriptions-item label="STAGE">{{ lot.stage }}</el-descriptions-item>
        <el-descriptions-item label="Bin">{{ lot.bin }}</el-descriptions-item>
        <el-descriptions-item label="Temperature">{{ lot.temperature }}°C</el-descriptions-item>
        <el-descriptions-item label="最终投入">{{ lot.final_stats.input_qty }}</el-descriptions-item>
        <el-descriptions-item label="最终良率">{{ lot.final_stats.yield_pct }}%</el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-for="(issue, i) in lot.validation_issues"
        :key="i"
        :title="issue.message"
        :type="issue.level === 'error' ? 'error' : 'warning'"
        show-icon
        :closable="false"
        style="margin-bottom: 8px"
      />

      <el-tabs v-model="activeTab">
        <el-tab-pane label="轮次概览" name="rounds">
          <LotRoundCharts :rounds="lot.rounds" />
          <el-card header="测试轮次" style="margin-top: 16px">
            <el-timeline>
              <el-timeline-item
                v-for="r in lot.rounds"
                :key="r.round_key"
                :timestamp="r.report_date || ''"
                placement="top"
              >
                <strong>{{ r.round_key }}</strong>
                — 投入 {{ r.input_qty }} · Pass {{ r.pass_count }} · Fail {{ r.fail_count }} · 良率 {{ r.yield_pct }}%
                <el-tag v-if="r.sub_file_count > 1" size="small" style="margin-left: 8px">
                  合并 {{ r.sub_file_count }} 子文件
                </el-tag>
              </el-timeline-item>
            </el-timeline>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="Bin/Site" name="analysis">
          <LotAnalysisCharts :lot="lot" />
        </el-tab-pane>

        <el-tab-pane label="芯片列表" name="dies">
          <el-form inline style="margin-bottom: 12px">
            <el-form-item label="轮次">
              <el-select v-model="dieRoundFilter" clearable placeholder="全部" style="width: 100px">
                <el-option v-for="r in lot.rounds" :key="r.round_key" :label="r.round_key" :value="r.round_key" />
              </el-select>
            </el-form-item>
            <el-checkbox v-model="onlyFail">仅 Fail</el-checkbox>
          </el-form>
          <el-table
            :data="filteredDies"
            size="small"
            stripe
            :row-class-name="({ row }) => row.boot_on === 'FAIL' ? 'fail-row' : ''"
          >
            <el-table-column prop="round_key" label="轮次" width="80" />
            <el-table-column prop="die_id" label="DieID" width="170">
              <template #default="{ row }">
                <DieIdLink :die-id="row.die_id" />
              </template>
            </el-table-column>
            <el-table-column prop="site" label="Site" width="60" />
            <el-table-column prop="booton" label="booton" min-width="140" show-overflow-tooltip />
            <el-table-column prop="tested" label="Tested" min-width="140" show-overflow-tooltip />
            <el-table-column prop="boot_on" label="结果" width="70" />
            <el-table-column prop="error_code" label="ErrorCode" width="90" />
            <el-table-column prop="log_status" label="Log" width="90">
              <template #default="{ row }">
                <el-tag :type="logStatusType(row.log_status)" size="small">
                  {{ logStatusLabel(row.log_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button
                  v-if="row.chip_log_id"
                  link
                  type="primary"
                  @click="openLog(row.chip_log_id, row.id)"
                >查看 Log</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="子文件/对账" name="files">
          <el-table :data="lot.sum_files" size="small">
            <el-table-column prop="filename" label="文件名" />
            <el-table-column prop="test_mode" label="Test Mode" width="100" />
            <el-table-column prop="round_key" label="Round" width="80" />
            <el-table-column prop="input_qty" label="投入" width="70" />
            <el-table-column prop="pass_count" label="Pass" width="70" />
            <el-table-column prop="fail_count" label="Fail" width="70" />
          </el-table>
          <el-button type="primary" style="margin-top: 16px" @click="$router.push(`/lots/${lotNo}/reconcile`)">
            打开对账页
          </el-button>
        </el-tab-pane>
      </el-tabs>
    </template>

    <ChipLogDrawer v-model="drawerOpen" :chip-log-id="activeLogId" :die-record-id="activeDieId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ChipLogDrawer from '../components/ChipLogDrawer.vue'
import DieIdLink from '../components/DieIdLink.vue'
import LotAnalysisCharts from '../components/LotAnalysisCharts.vue'
import LotRoundCharts from '../components/LotRoundCharts.vue'
import { getLot, getRoundDies, type LotDetail, type RoundDie } from '../api'
import { materialKey, materialLabel } from '../utils/material'
import { parseRoundOrder } from '../utils/roundOrder'

const route = useRoute()
const lotNo = ref(route.params.lotNo as string)
const stageQuery = computed(() => (route.query.stage as string) || undefined)
const lot = ref<LotDetail | null>(null)
const loading = ref(false)
const activeTab = ref('rounds')
const roundDies = reactive<Record<string, RoundDie[]>>({})
const dieRoundFilter = ref('')
const onlyFail = ref(false)
const drawerOpen = ref(false)
const activeLogId = ref<number | null>(null)
const activeDieId = ref<number | null>(null)

const materialGroupKey = computed(() => (lot.value ? materialKey(lot.value.lot_no) : ''))
const materialGroupLabel = computed(() => materialLabel(materialGroupKey.value))

const allDies = computed(() => {
  const list: (RoundDie & { round_key: string })[] = []
  if (!lot.value) return list
  for (const r of lot.value.rounds) {
    for (const d of roundDies[r.round_key] || []) {
      list.push({ ...d, round_key: r.round_key })
    }
  }
  return list
})

const filteredDies = computed(() => {
  let rows = allDies.value
  if (dieRoundFilter.value) rows = rows.filter((d) => d.round_key === dieRoundFilter.value)
  if (onlyFail.value) rows = rows.filter((d) => d.boot_on === 'FAIL')
  return [...rows].sort((a, b) => {
    const byDie = a.die_id.localeCompare(b.die_id)
    if (byDie !== 0) return byDie
    const [ta, na] = parseRoundOrder(a.round_key)
    const [tb, nb] = parseRoundOrder(b.round_key)
    if (ta !== tb) return ta - tb
    return na - nb
  })
})

function logStatusType(s: string) {
  if (s === 'linked') return 'success'
  if (s === 'mismatch') return 'danger'
  return 'warning'
}

function logStatusLabel(s: string) {
  const map: Record<string, string> = { linked: '已关联', missing: '缺失', mismatch: '不一致' }
  return map[s] || s
}

async function loadRoundDies(roundKey: string, failOnly = false) {
  roundDies[roundKey] = await getRoundDies(lotNo.value, roundKey, {
    only_fail: failOnly,
    stage: stageQuery.value,
  })
}

async function load() {
  loading.value = true
  try {
    lot.value = await getLot(lotNo.value, stageQuery.value)
    if (lot.value?.rounds.length) {
      for (const r of lot.value.rounds) {
        await loadRoundDies(r.round_key)
      }
    }
    if (route.query.tab) activeTab.value = route.query.tab as string
    if (route.query.only_fail === '1') onlyFail.value = true
    if (route.query.round) dieRoundFilter.value = route.query.round as string
  } finally {
    loading.value = false
  }
}

function openLog(chipLogId?: number, dieId?: number) {
  activeLogId.value = chipLogId ?? null
  activeDieId.value = dieId ?? null
  drawerOpen.value = true
}

onMounted(load)
watch(() => [route.params.lotNo, route.query.stage], () => {
  lotNo.value = route.params.lotNo as string
  load()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
:deep(.fail-row) {
  background-color: #fef0f0;
}
</style>

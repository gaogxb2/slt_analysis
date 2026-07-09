<template>
  <div v-loading="loading">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h2 class="page-title" style="margin: 0">SUM / Log 对账 — {{ lotNo }}</h2>
      <el-button @click="$router.push(`/lots/${lotNo}`)">返回 LOT 详情</el-button>
    </div>

    <el-form inline>
      <el-form-item label="Test Mode">
        <el-select v-model="filters.test_mode" clearable placeholder="全部" style="width: 120px">
          <el-option v-for="m in testModes" :key="m" :label="m" :value="m" />
        </el-select>
      </el-form-item>
      <el-form-item label="轮次">
        <el-select v-model="filters.round_key" clearable placeholder="全部" style="width: 100px">
          <el-option v-for="r in roundKeys" :key="r" :label="r" :value="r" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="filters.only_fail">仅 Fail</el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="filters.only_abnormal">仅异常</el-checkbox>
      </el-form-item>
      <el-button type="primary" @click="load">筛选</el-button>
      <el-button @click="exportCsv" :disabled="!data?.rows.length">导出 CSV</el-button>
    </el-form>

    <el-row :gutter="12" v-if="data" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">已匹配</div>
          <div class="stat-value ok">{{ data.summary.matched_count }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">SUM 无 Log</div>
          <div class="stat-value warn">{{ data.summary.sum_only_count }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">Log 无 SUM</div>
          <div class="stat-value muted">{{ data.summary.log_only_count }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">字段不一致</div>
          <div class="stat-value err">{{ data.summary.mismatch_count }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-table :data="data?.rows || []" stripe size="small">
      <el-table-column prop="die_id" label="DieID" width="170">
        <template #default="{ row }">
          <DieIdLink :die-id="row.die_id" />
        </template>
      </el-table-column>
      <el-table-column prop="test_mode" label="TestMode" width="90" />
      <el-table-column prop="site" label="Site" width="60" />
      <el-table-column prop="sum_boot_on" label="SUM BootOn" width="100" />
      <el-table-column prop="log_pf" label="Log P_F" width="80" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="diff_summary" label="差异摘要" min-width="120" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.chip_log_id"
            link
            type="primary"
            @click="openLog(row.chip_log_id)"
          >查看 Log</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-card header="字段说明" style="margin-top: 16px" shadow="never">
      <p><strong>SUM 独有</strong>：Tj、Temperature、BiosTime、ErrorCode 等（Log 中无对应项）</p>
      <p><strong>Log 独有</strong>：ONETEST 明细、第二组+ DieID、Wafer X/Y 等</p>
    </el-card>

    <ChipLogDrawer v-model="drawerOpen" :chip-log-id="activeLogId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ChipLogDrawer from '../components/ChipLogDrawer.vue'
import DieIdLink from '../components/DieIdLink.vue'
import { getReconcile, type ReconcileResult } from '../api'

const route = useRoute()
const lotNo = ref(route.params.lotNo as string)
const loading = ref(false)
const data = ref<ReconcileResult | null>(null)
const drawerOpen = ref(false)
const activeLogId = ref<number | null>(null)

const filters = reactive({
  test_mode: '',
  round_key: '',
  only_fail: false,
  only_abnormal: false,
})

const testModes = computed(() => {
  const s = new Set<string>()
  data.value?.rows.forEach((r) => { if (r.test_mode) s.add(r.test_mode) })
  return [...s].sort()
})

const roundKeys = computed(() => {
  const s = new Set<string>()
  data.value?.rows.forEach((r) => { if (r.round_key) s.add(r.round_key) })
  return [...s].sort()
})

function statusType(s: string) {
  if (s === 'matched') return 'success'
  if (s === 'sum_only') return 'warning'
  if (s === 'log_only') return 'info'
  return 'danger'
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    matched: '已匹配',
    sum_only: 'SUM无Log',
    log_only: 'Log无SUM',
    mismatch: '不一致',
  }
  return map[s] || s
}

async function load() {
  loading.value = true
  try {
    data.value = await getReconcile(lotNo.value, {
      test_mode: filters.test_mode || undefined,
      round_key: filters.round_key || undefined,
      only_fail: filters.only_fail,
      only_abnormal: filters.only_abnormal,
    })
  } finally {
    loading.value = false
  }
}

function openLog(id: number) {
  activeLogId.value = id
  drawerOpen.value = true
}

function exportCsv() {
  if (!data.value) return
  const header = ['die_id', 'test_mode', 'site', 'sum_boot_on', 'log_pf', 'status', 'diff_summary']
  const lines = [header.join(',')]
  for (const r of data.value.rows) {
    lines.push(header.map((h) => (r as Record<string, unknown>)[h] ?? '').join(','))
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `reconcile_${lotNo.value}.csv`
  a.click()
}

onMounted(load)
watch(() => route.params.lotNo, (v) => {
  lotNo.value = v as string
  load()
})
</script>

<style scoped>
.stat-label { font-size: 12px; color: #909399; }
.stat-value { font-size: 24px; font-weight: 600; margin-top: 4px; }
.stat-value.ok { color: #67c23a; }
.stat-value.warn { color: #e6a23c; }
.stat-value.muted { color: #909399; }
.stat-value.err { color: #f56c6c; }
</style>

<template>
  <div>
    <h2 class="page-title">总览 Dashboard</h2>

    <el-form inline class="filter-bar">
      <el-form-item label="LOT NO.">
        <el-select
          v-model="filterLot"
          filterable
          clearable
          allow-create
          default-first-option
          placeholder="选择或输入 LOT"
          style="width: 200px"
        >
          <el-option v-for="opt in lotOptions" :key="opt" :label="opt" :value="opt" />
        </el-select>
      </el-form-item>
      <el-form-item label="STAGE">
        <el-input v-model="filterStage" clearable placeholder="如 MT2" style="width: 100px" />
      </el-form-item>
      <el-button type="primary" @click="load">查询</el-button>
      <el-button @click="resetFilter">重置</el-button>
    </el-form>

    <div class="stat-cards" v-if="data">
      <div class="stat-card"><div class="label">批次数</div><div class="value">{{ data.lot_count }}</div></div>
      <div class="stat-card"><div class="label">总投入</div><div class="value">{{ data.total_input }}</div></div>
      <div class="stat-card"><div class="label">最终 Pass</div><div class="value">{{ data.total_final_pass }}</div></div>
      <div class="stat-card"><div class="label">平均良率</div><div class="value">{{ data.avg_yield_pct }}%</div></div>
      <div class="stat-card fail-types-card">
        <div class="label">最终 Fail 类型</div>
        <div class="fail-tags" v-if="data.final_fail_breakdown.length">
          <el-tag v-for="f in data.final_fail_breakdown" :key="f.description" type="danger" size="small">
            {{ f.description }}: {{ f.count }}
          </el-tag>
        </div>
        <div class="value" v-else style="font-size: 14px; color: #909399">无</div>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card header="LOT 良率">
          <div ref="yieldChart" style="height: 320px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="最终 Fail 类型分布（仍未 Pass）">
          <div ref="failChart" style="height: 320px" />
        </el-card>
      </el-col>
    </el-row>

    <el-card header="LOT 摘要" style="margin-top: 16px">
      <el-table :data="data?.lots || []" stripe @row-click="goLot">
        <el-table-column prop="lot_no" label="LOT NO." width="130" />
        <el-table-column prop="stage" label="STAGE" width="80" />
        <el-table-column prop="input_qty" label="初测投入" width="90" />
        <el-table-column prop="final_pass" label="Pass" width="70" />
        <el-table-column
          v-for="desc in failTypeColumns"
          :key="desc"
          :label="desc"
          width="72"
          align="center"
        >
          <template #default="{ row }">{{ failCount(row, desc) }}</template>
        </el-table-column>
        <el-table-column prop="final_fail" label="Fail 合计" width="90" />
        <el-table-column label="良率" width="80">
          <template #default="{ row }">{{ row.final_yield_pct }}%</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getLots, getOverview, type LotSummary } from '../api'
import { materialKey, materialPath } from '../utils/material'

const router = useRouter()
const data = ref<Awaited<ReturnType<typeof getOverview>> | null>(null)
const filterLot = ref('')
const filterStage = ref('')
const lotOptions = ref<string[]>([])
const yieldChart = ref<HTMLElement>()
const failChart = ref<HTMLElement>()

const failTypeColumns = computed(() => {
  const set = new Set<string>()
  data.value?.lots.forEach((l) =>
    l.final_fail_breakdown.forEach((f) => set.add(f.description)),
  )
  data.value?.final_fail_breakdown.forEach((f) => set.add(f.description))
  return Array.from(set).sort()
})

function failCount(row: LotSummary, desc: string) {
  const item = row.final_fail_breakdown.find((f) => f.description === desc)
  return item?.count ?? 0
}

function goLot(row: LotSummary) {
  router.push(materialPath(materialKey(row.lot_no)))
}

async function load() {
  data.value = await getOverview({
    lot_no: filterLot.value || undefined,
    stage: filterStage.value || undefined,
  })
  drawCharts()
}

function resetFilter() {
  filterLot.value = ''
  filterStage.value = ''
  load()
}

function drawCharts() {
  if (!data.value) return
  const lots = data.value.lots

  if (yieldChart.value) {
    const existing = echarts.getInstanceByDom(yieldChart.value)
    if (existing) existing.dispose()
    const c = echarts.init(yieldChart.value)
    c.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: lots.map((l) => l.lot_no),
        axisLabel: { rotate: lots.length > 3 ? 30 : 0 },
      },
      yAxis: { type: 'value', max: 100 },
      series: [{
        type: 'bar',
        data: lots.map((l) => l.final_yield_pct),
        itemStyle: { color: '#409eff' },
      }],
    })
  }

  if (failChart.value) {
    const existing = echarts.getInstanceByDom(failChart.value)
    if (existing) existing.dispose()
    const breakdown = data.value.final_fail_breakdown
    const c = echarts.init(failChart.value)
    if (!breakdown.length) {
      c.setOption({
        title: { text: '无 Fail', left: 'center', top: 'center', textStyle: { color: '#909399', fontSize: 14 } },
      })
      return
    }
    c.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: breakdown.map((f) => f.description) },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{
        type: 'bar',
        data: breakdown.map((f) => f.count),
        itemStyle: { color: '#f56c6c' },
        label: { show: true, position: 'top' },
      }],
    })
  }
}

onMounted(async () => {
  const lots = await getLots()
  lotOptions.value = lots.map((l) => l.lot_no)
  await load()
})

watch(data, () => drawCharts())
</script>

<style scoped>
.filter-bar {
  margin-bottom: 16px;
  background: #fff;
  padding: 12px 12px 0;
  border-radius: 8px;
  border: 1px solid #ebeef5;
}
.fail-types-card .fail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.fail-types-card .value {
  margin-top: 4px;
}
</style>

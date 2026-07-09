<template>
  <div>
    <h2 class="page-title">Bin / Site 分析</h2>
    <el-form inline>
      <el-form-item label="LOT">
        <el-select v-model="selectedLot" placeholder="选择 LOT" @change="loadLot">
          <el-option v-for="l in lotOptions" :key="l.lot_no" :label="l.lot_no" :value="l.lot_no" />
        </el-select>
      </el-form-item>
    </el-form>
    <el-row :gutter="16" v-if="lot">
      <el-col :span="12">
        <el-card header="Site 良率（各轮）">
          <div ref="siteChart" style="height: 360px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="Fail Pareto（最后一轮）">
          <div ref="paretoChart" style="height: 360px" />
        </el-card>
      </el-col>
    </el-row>
    <el-card header="Bin 跨轮热力表" style="margin-top: 16px" v-if="lot">
      <el-table :data="heatRows" size="small">
        <el-table-column prop="description" label="Bin" width="100" />
        <el-table-column v-for="rk in roundKeys" :key="rk" :label="rk" width="90">
          <template #default="{ row }">{{ row.counts[rk] ?? 0 }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { getLots, getLot, type LotDetail } from '../api'

const lotOptions = ref<Awaited<ReturnType<typeof getLots>>>([])
const selectedLot = ref('')
const lot = ref<LotDetail | null>(null)
const siteChart = ref<HTMLElement>()
const paretoChart = ref<HTMLElement>()

const roundKeys = computed(() => lot.value?.rounds.map((r) => r.round_key) ?? [])

const heatRows = computed(() => {
  if (!lot.value) return []
  const map: Record<string, Record<string, number>> = {}
  for (const r of lot.value.rounds) {
    for (const b of r.bin_summaries) {
      const key = b.description
      if (!map[key]) map[key] = {}
      map[key][r.round_key] = b.count
    }
  }
  return Object.entries(map).map(([description, counts]) => ({ description, counts }))
})

async function loadLot() {
  if (!selectedLot.value) return
  lot.value = await getLot(selectedLot.value)
  drawCharts()
}

function drawCharts() {
  if (!lot.value) return
  const rounds = lot.value.rounds
  if (siteChart.value && rounds.length) {
    const last = rounds[rounds.length - 1]
    const c = echarts.init(siteChart.value)
    c.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: rounds.map((r) => r.round_key) },
      xAxis: { type: 'category', data: last.site_counters.map((s) => `Site${s.site_no}`) },
      yAxis: { type: 'value', max: 100 },
      series: rounds.map((r) => ({
        name: r.round_key,
        type: 'line',
        data: r.site_counters.map((s) => s.yield_pct),
      })),
    })
  }
  if (paretoChart.value && rounds.length) {
    const last = rounds[rounds.length - 1]
    const fails = last.bin_summaries.filter((b) => b.description !== 'PASS')
    const c = echarts.init(paretoChart.value)
    c.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: fails.map((f) => f.description) },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: fails.map((f) => f.count), itemStyle: { color: '#f56c6c' } }],
    })
  }
}

onMounted(async () => {
  lotOptions.value = await getLots()
  if (lotOptions.value.length) {
    selectedLot.value = lotOptions.value[0].lot_no
    await loadLot()
  }
})

watch(lot, () => drawCharts())
</script>

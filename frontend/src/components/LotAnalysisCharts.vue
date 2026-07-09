<template>
  <el-row :gutter="16">
    <el-col :span="12">
      <el-card header="Site 良率（各轮）">
        <div ref="siteChartEl" style="height: 360px" />
      </el-card>
    </el-col>
    <el-col :span="12">
      <el-card header="Fail Pareto（最后一轮）">
        <div ref="paretoChartEl" style="height: 360px" />
      </el-card>
    </el-col>
  </el-row>
  <el-card header="Bin 跨轮热力表" style="margin-top: 16px">
    <el-table :data="heatRows" size="small">
      <el-table-column prop="description" label="Bin" width="100" />
      <el-table-column v-for="rk in roundKeys" :key="rk" :label="rk" width="90">
        <template #default="{ row }">{{ row.counts[rk] ?? 0 }}</template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { LotDetail } from '../api'

const props = defineProps<{ lot: LotDetail }>()

const siteChartEl = ref<HTMLElement>()
const paretoChartEl = ref<HTMLElement>()

const roundKeys = computed(() => props.lot.rounds.map((r) => r.round_key))

const heatRows = computed(() => {
  const map: Record<string, Record<string, number>> = {}
  for (const r of props.lot.rounds) {
    for (const b of r.bin_summaries) {
      if (!map[b.description]) map[b.description] = {}
      map[b.description][r.round_key] = b.count
    }
  }
  return Object.entries(map).map(([description, counts]) => ({ description, counts }))
})

function drawCharts() {
  const rounds = props.lot.rounds
  if (siteChartEl.value && rounds.length) {
    const last = rounds[rounds.length - 1]
    const existing = echarts.getInstanceByDom(siteChartEl.value)
    if (existing) existing.dispose()
    const c = echarts.init(siteChartEl.value)
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
  if (paretoChartEl.value && rounds.length) {
    const last = rounds[rounds.length - 1]
    const fails = last.bin_summaries.filter((b) => b.description !== 'PASS')
    const existing = echarts.getInstanceByDom(paretoChartEl.value)
    if (existing) existing.dispose()
    const c = echarts.init(paretoChartEl.value)
    c.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: fails.map((f) => f.description) },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: fails.map((f) => f.count), itemStyle: { color: '#f56c6c' } }],
    })
  }
}

onMounted(drawCharts)
watch(() => props.lot, drawCharts, { deep: true })
</script>

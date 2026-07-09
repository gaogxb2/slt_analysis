<template>
  <el-row :gutter="16">
    <el-col :span="12">
      <div ref="yieldChartEl" style="height: 280px" />
    </el-col>
    <el-col :span="12">
      <div ref="failChartEl" style="height: 280px" />
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { TestRound } from '../api'

const props = defineProps<{ rounds: TestRound[] }>()

const yieldChartEl = ref<HTMLElement>()
const failChartEl = ref<HTMLElement>()

function draw() {
  const rounds = props.rounds
  if (yieldChartEl.value) {
    const existing = echarts.getInstanceByDom(yieldChartEl.value)
    if (existing) existing.dispose()
    const c = echarts.init(yieldChartEl.value)
    c.setOption({
      title: { text: '各轮良率', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: rounds.map((r) => r.round_key) },
      yAxis: { type: 'value', max: 100 },
      series: [{
        type: 'line',
        data: rounds.map((r) => r.yield_pct),
        itemStyle: { color: '#409eff' },
        label: { show: true, formatter: '{c}%' },
      }],
    })
  }
  if (failChartEl.value) {
    const failTypes = new Set<string>()
    for (const r of rounds) {
      for (const b of r.bin_summaries) {
        if (b.description !== 'PASS') failTypes.add(b.description)
      }
    }
    const types = [...failTypes].sort()
    const existing = echarts.getInstanceByDom(failChartEl.value)
    if (existing) existing.dispose()
    const c = echarts.init(failChartEl.value)
    c.setOption({
      title: { text: '各轮 Fail 类型', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      legend: { data: types, bottom: 0 },
      xAxis: { type: 'category', data: rounds.map((r) => r.round_key) },
      yAxis: { type: 'value', minInterval: 1 },
      series: types.map((t) => ({
        name: t,
        type: 'bar',
        stack: 'fail',
        data: rounds.map((r) => {
          const b = r.bin_summaries.find((x) => x.description === t)
          return b?.count ?? 0
        }),
      })),
    })
  }
}

onMounted(draw)
watch(() => props.rounds, draw, { deep: true })
</script>

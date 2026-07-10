<template>
  <div class="yield-category-block">
    <div class="category-panel">
      <div class="category-title">MT 温度分类（SUM 初轮良率）</div>
      <div class="category-header">
        <span class="col-process">工序</span>
        <span v-for="cat in TEMP_LABELS" :key="cat" class="col-temp">{{ cat }}</span>
      </div>
      <div v-for="stage in sortedStages" :key="stage" class="category-row">
        <span class="col-process">{{ stage }}</span>
        <el-radio-group v-model="categoryMap[stage]" class="temp-radios" @change="onCategoryChange">
          <el-radio v-for="cat in TEMP_LABELS" :key="cat" :value="cat" />
        </el-radio-group>
      </div>
      <div v-if="categoryError" class="category-error">{{ categoryError }}</div>
      <div class="category-hint">总 Yield = 常温 Yield × 低温 Yield × 高温 Yield（与 slt_yield 一致）</div>
    </div>

    <el-tabs v-model="activeTab" class="chart-tabs">
      <el-tab-pane label="全部工序" name="all">
        <div ref="allChartRef" class="chart-box" />
      </el-tab-pane>
      <el-tab-pane label="温度分类" name="cat">
        <div ref="catChartRef" class="chart-box" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { MaterialMember } from '../api'
import {
  TEMP_LABELS,
  CATEGORY_COLORS,
  TOTAL_YIELD_COLOR,
  applyCategoryMap,
  calcCategoryYield,
  calcTotalYield,
  fmtPct,
  getTestQtyByCategory,
  loadCategoryMap,
  membersToProcessRows,
  saveCategoryMap,
  sortProcesses,
  validateCategories,
  type TempLabel,
} from '../utils/yieldCategory'

const props = defineProps<{
  materialKey: string
  members: MaterialMember[]
}>()

const activeTab = ref('all')
const allChartRef = ref<HTMLElement>()
const catChartRef = ref<HTMLElement>()
const categoryError = ref('')

const sortedStages = computed(() =>
  sortProcesses([...new Set(props.members.map((m) => m.stage))]),
)

const categoryMap = ref<Record<string, TempLabel>>(
  loadCategoryMap(props.materialKey, sortedStages.value),
)

const processRows = computed(() =>
  applyCategoryMap(membersToProcessRows(props.members), categoryMap.value),
)

function onCategoryChange() {
  categoryError.value = validateCategories(categoryMap.value) ?? ''
  saveCategoryMap(props.materialKey, categoryMap.value)
  drawCharts()
}

function disposeChart(el?: HTMLElement) {
  if (el) echarts.getInstanceByDom(el)?.dispose()
}

function drawAllChart() {
  const el = allChartRef.value
  if (!el) return
  disposeChart(el)
  const rows = processRows.value
  if (!rows.length) return

  const stages = sortProcesses(rows.map((r) => r.process))
  const totalYield = calcTotalYield(rows)
  const testQtys = stages.map((s) => rows.find((r) => r.process === s)?.testQty ?? 0)
  const yieldData = stages.map((stage) => {
    const row = rows.find((r) => r.process === stage)!
    return {
      value: row.yield,
      itemStyle: { color: CATEGORY_COLORS[row.tempType] },
    }
  })
  const lineData = stages.map((stage) => rows.find((r) => r.process === stage)!.yield)

  const c = echarts.init(el)
  c.setOption({
    title: {
      text: '各 MT 初轮良率及总 Yield（总 Yield = 常温 × 低温 × 高温）',
      left: 'center',
      textStyle: { fontSize: 13 },
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const items = params as Array<{ seriesName: string; data: number | { value: number }; axisValue: string }>
        let html = `${items[0]?.axisValue ?? ''}<br/>`
        for (const p of items) {
          const raw = typeof p.data === 'object' && p.data ? p.data.value : p.data
          if (raw === null || raw === undefined) continue
          const val = p.seriesName === 'TestQty' ? String(raw) : fmtPct(raw as number)
          html += `${p.seriesName}: ${val}<br/>`
        }
        if (totalYield !== null) {
          html += `总Yield: ${fmtPct(totalYield)}`
        }
        return html
      },
    },
    grid: { left: 56, right: 56, top: 56, bottom: 48 },
    xAxis: { type: 'category', data: stages },
    yAxis: [
      { type: 'value', name: 'Yield', min: 0, max: 1, axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` } },
      { type: 'value', name: 'TestQty', position: 'right', axisLabel: { formatter: (v: number) => v.toLocaleString() } },
    ],
    legend: {
      top: 28,
      data: [...stages, '总Yield', 'TestQty'],
      type: 'scroll',
    },
    series: [
      {
        name: 'TestQty',
        type: 'bar',
        yAxisIndex: 1,
        data: testQtys,
        barWidth: '55%',
        itemStyle: { color: 'rgba(136,136,136,0.22)' },
        z: 1,
      },
      {
        name: 'Yield',
        type: 'bar',
        yAxisIndex: 0,
        data: yieldData,
        barGap: '-100%',
        barWidth: '40%',
        label: {
          show: true,
          position: 'top',
          formatter: (p: { data: { value: number } }) => fmtPct(p.data.value),
          fontSize: 10,
        },
        z: 2,
      },
      {
        name: '工序趋势',
        type: 'line',
        yAxisIndex: 0,
        data: lineData,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 1.5, color: '#909399' },
        itemStyle: { color: '#909399' },
        z: 3,
      },
      {
        name: '总Yield',
        type: 'line',
        yAxisIndex: 0,
        data: [],
        markLine: totalYield !== null ? {
          symbol: 'none',
          lineStyle: { type: 'dashed', color: TOTAL_YIELD_COLOR, width: 2.5 },
          label: { formatter: `总Yield ${fmtPct(totalYield)}`, color: TOTAL_YIELD_COLOR, fontSize: 11 },
          data: [{ yAxis: totalYield }],
        } : undefined,
        z: 4,
      },
    ],
  })
}

function drawCategoryChart() {
  const el = catChartRef.value
  if (!el) return
  disposeChart(el)
  const rows = processRows.value
  if (!rows.length) return

  const stages = sortProcesses(rows.map((r) => r.process))
  const catTestQty = getTestQtyByCategory(rows)
  const totalYield = calcTotalYield(rows)

  const categoryYields = TEMP_LABELS.map((cat) => calcCategoryYield(rows, cat))

  const c = echarts.init(el)
  c.setOption({
    title: {
      text: '常温 / 低温 / 高温 合并良率及总 Yield',
      left: 'center',
      textStyle: { fontSize: 13 },
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const items = params as Array<{ seriesName: string; data: number | null; color: string }>
        let html = '汇总<br/>'
        for (const p of items) {
          if (p.data === null || p.data === undefined) continue
          const isQty = p.seriesName.endsWith('TestQty')
          const val = isQty ? String(p.data) : fmtPct(p.data as number)
          html += `<span style="color:${p.color}">●</span> ${p.seriesName}: ${val}<br/>`
        }
        return html
      },
    },
    grid: { left: 56, right: 120, top: 56, bottom: 48 },
    xAxis: { type: 'category', data: ['合并'] },
    yAxis: [
      { type: 'value', name: 'Yield', min: 0, max: 1, axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` } },
      { type: 'value', name: 'TestQty', position: 'right', axisLabel: { formatter: (v: number) => v.toLocaleString() } },
    ],
    legend: { top: 28, type: 'scroll' },
    series: [
      ...TEMP_LABELS.map((cat, idx) => ({
        name: `${cat}TestQty`,
        type: 'bar' as const,
        stack: 'qty',
        yAxisIndex: 1,
        data: [catTestQty[cat]],
        itemStyle: { color: CATEGORY_COLORS[cat], opacity: 0.22 },
        barWidth: '55%',
        z: 1,
      })),
      ...TEMP_LABELS.map((cat, idx) => ({
        name: `${cat}工序`,
        type: 'line' as const,
        yAxisIndex: 0,
        data: [categoryYields[idx]],
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 2, color: CATEGORY_COLORS[cat] },
        itemStyle: { color: CATEGORY_COLORS[cat] },
        label: {
          show: true,
          formatter: (p: { data: number | null }) => fmtPct(p.data),
          position: 'top',
          color: CATEGORY_COLORS[cat],
          fontSize: 10,
        },
        z: 3,
      })),
      {
        name: '总Yield',
        type: 'line',
        yAxisIndex: 0,
        data: [totalYield],
        symbol: 'rect',
        symbolSize: 10,
        lineStyle: { type: 'dashed', width: 2.5, color: TOTAL_YIELD_COLOR },
        itemStyle: { color: TOTAL_YIELD_COLOR },
        label: {
          show: true,
          formatter: () => fmtPct(totalYield),
          position: 'bottom',
          color: TOTAL_YIELD_COLOR,
          fontSize: 11,
        },
        z: 3,
      },
    ],
  })
}

function drawCharts() {
  categoryError.value = validateCategories(categoryMap.value) ?? ''
  drawAllChart()
  drawCategoryChart()
}

watch(
  () => [props.members, props.materialKey] as const,
  async () => {
    categoryMap.value = loadCategoryMap(props.materialKey, sortedStages.value)
    await nextTick()
    drawCharts()
  },
  { deep: true, immediate: true },
)

watch(activeTab, async () => {
  await nextTick()
  drawCharts()
})

onBeforeUnmount(() => {
  disposeChart(allChartRef.value)
  disposeChart(catChartRef.value)
})
</script>

<style scoped>
.yield-category-block {
  margin-top: 16px;
  border-top: 1px solid #ebeef5;
  padding-top: 16px;
}
.category-panel {
  background: #fafafa;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 12px;
}
.category-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 10px;
}
.category-header,
.category-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.category-header {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
}
.col-process {
  width: 72px;
  flex-shrink: 0;
}
.col-temp {
  width: 88px;
  text-align: center;
}
.temp-radios {
  display: flex;
  gap: 48px;
}
.temp-radios :deep(.el-radio) {
  margin-right: 0;
}
.category-error {
  color: #f56c6c;
  font-size: 12px;
  margin-top: 6px;
}
.category-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}
.chart-box {
  height: 340px;
  width: 100%;
}
.chart-tabs {
  margin-top: 4px;
}
</style>

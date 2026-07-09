<template>
  <div>
    <h2 class="page-title">物料批次</h2>

    <el-card class="picker-card" shadow="never">
      <el-row :gutter="16" align="middle">
        <el-col :span="14">
          <div class="picker-label">选择物料族（可多选）</div>
          <el-select
            v-model="selectedKeys"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            placeholder="从目录中选择物料族"
            style="width: 100%"
            :loading="catalogLoading"
          >
            <el-option
              v-for="item in catalogOptions"
              :key="item.material_key"
              :label="optionLabel(item)"
              :value="item.material_key"
            />
          </el-select>
          <div class="picker-hint">目录共 {{ catalog.length }} 个物料族，已选 {{ selectedKeys.length }} 个</div>
        </el-col>
        <el-col :span="10">
          <div class="picker-label">搜索缩小目录</div>
          <el-input
            v-model="catalogSearch"
            clearable
            placeholder="物料族 / LOT NO. / STAGE"
            @input="onCatalogSearch"
          />
          <div class="picker-actions">
            <el-button type="primary" :disabled="!selectedKeys.length" :loading="loading" @click="applyAnalysis">
              查看分析
            </el-button>
            <el-button @click="clearSelection">清空</el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <div v-loading="loading">
      <el-empty
        v-if="!loading && !displayedGroups.length"
        description="请在左侧选择物料族，点击「查看分析」后展示图表与明细"
      />

      <el-card
        v-for="g in displayedGroups"
        :key="g.material_key"
        style="margin-bottom: 20px"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span class="material-title">物料族 {{ g.material_label }}</span>
            <el-tag size="small">{{ g.member_count }} 个子批次</el-tag>
          </div>
        </template>

        <div class="member-tags">
          <el-tag
            v-for="m in g.members"
            :key="`${m.lot_no}-${m.stage}`"
            class="member-tag"
            effect="plain"
            @click="goLot(m.lot_no, m.stage)"
          >
            {{ m.lot_no }} ({{ m.stage }}) · 良率 {{ m.final_yield_pct }}%
          </el-tag>
        </div>

        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="12">
            <div :ref="(el) => setYieldRef(g.material_key, el as HTMLElement)" style="height: 300px" />
          </el-col>
          <el-col :span="12">
            <div :ref="(el) => setFailRef(g.material_key, el as HTMLElement)" style="height: 300px" />
          </el-col>
        </el-row>

        <el-table :data="g.round_rows" size="small" stripe style="margin-top: 16px">
          <el-table-column prop="label" label="批次/轮次（复测明细）" min-width="200">
            <template #default="{ row }">
              <el-button link type="primary" @click="goLot(row.lot_no, row.stage)">
                {{ row.label }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column prop="input_qty" label="投入" width="70" />
          <el-table-column prop="pass_count" label="Pass" width="70" />
          <el-table-column prop="fail_count" label="Fail" width="70">
            <template #default="{ row }">
              <el-button
                v-if="row.fail_count > 0"
                link
                type="danger"
                @click="goLotFail(row.lot_no, row.stage)"
              >{{ row.fail_count }}</el-button>
              <span v-else>0</span>
            </template>
          </el-table-column>
          <el-table-column label="良率" width="80">
            <template #default="{ row }">{{ row.yield_pct }}%</template>
          </el-table-column>
          <el-table-column label="Fail 分布" min-width="160">
            <template #default="{ row }">
              <el-tag
                v-for="f in row.fail_bins"
                :key="f.description"
                size="small"
                type="danger"
                style="margin-right: 4px"
              >{{ f.description }}: {{ f.count }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getMaterialCatalog, getMaterialGroups, type MaterialGroup, type MaterialGroupSummary } from '../api'
import { lotDetailPath } from '../utils/material'

const route = useRoute()
const router = useRouter()
const catalogLoading = ref(false)
const loading = ref(false)
const catalog = ref<MaterialGroupSummary[]>([])
const catalogSearch = ref('')
const selectedKeys = ref<string[]>([])
const displayedGroups = ref<MaterialGroup[]>([])

let searchTimer: ReturnType<typeof setTimeout> | undefined

const yieldRefs: Record<string, HTMLElement | undefined> = {}
const failRefs: Record<string, HTMLElement | undefined> = {}

const catalogOptions = computed(() => catalog.value)

function optionLabel(item: MaterialGroupSummary) {
  const lots = item.lot_nos.slice(0, 3).join(', ')
  const more = item.lot_nos.length > 3 ? ` 等${item.lot_nos.length}个LOT` : ''
  return `${item.material_label}（${item.member_count} 子批次 · ${lots}${more}）`
}

function setYieldRef(key: string, el: HTMLElement | null) {
  if (el) yieldRefs[key] = el
}
function setFailRef(key: string, el: HTMLElement | null) {
  if (el) failRefs[key] = el
}

function goLot(lotNo: string, stage: string) {
  router.push(lotDetailPath(lotNo, stage))
}

function goLotFail(lotNo: string, stage: string) {
  const params = new URLSearchParams({ stage, tab: 'dies', only_fail: '1' })
  router.push(`/lots/${encodeURIComponent(lotNo)}?${params}`)
}

async function loadCatalog() {
  catalogLoading.value = true
  try {
    catalog.value = await getMaterialCatalog({
      search: catalogSearch.value || undefined,
    })
  } finally {
    catalogLoading.value = false
  }
}

function onCatalogSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadCatalog, 300)
}

function clearSelection() {
  selectedKeys.value = []
  displayedGroups.value = []
  disposeCharts()
}

function disposeCharts() {
  for (const el of Object.values(yieldRefs)) {
    if (el) echarts.getInstanceByDom(el)?.dispose()
  }
  for (const el of Object.values(failRefs)) {
    if (el) echarts.getInstanceByDom(el)?.dispose()
  }
}

async function applyAnalysis() {
  if (!selectedKeys.value.length) return
  loading.value = true
  disposeCharts()
  try {
    displayedGroups.value = await getMaterialGroups({
      material_keys: selectedKeys.value.join(','),
    })
    await nextTick()
    drawAllCharts()
  } finally {
    loading.value = false
  }
}

function memberLabel(m: { lot_no: string; stage: string }) {
  return `${m.lot_no} (${m.stage})`
}

function drawAllCharts() {
  for (const g of displayedGroups.value) {
    const memberLabels = g.members.map(memberLabel)
    const yEl = yieldRefs[g.material_key]
    if (yEl) {
      const ex = echarts.getInstanceByDom(yEl)
      if (ex) ex.dispose()
      const c = echarts.init(yEl)
      c.setOption({
        title: { text: '子批次良率（含复测后最终结果）', left: 'center', textStyle: { fontSize: 13 } },
        tooltip: {
          trigger: 'axis',
          formatter: (params: unknown) => {
            const p = (params as { dataIndex: number }[])[0]
            const m = g.members[p.dataIndex]
            return `${memberLabel(m)}<br/>良率 ${m.final_yield_pct}%<br/>Pass ${m.final_pass} / 投入 ${m.input_qty}`
          },
        },
        xAxis: { type: 'category', data: memberLabels, axisLabel: { rotate: 20, fontSize: 10 } },
        yAxis: { type: 'value', max: 100 },
        series: [{
          type: 'bar',
          data: g.members.map((m) => m.final_yield_pct),
          itemStyle: { color: '#409eff' },
          label: { show: true, position: 'top', formatter: '{c}%' },
        }],
      })
    }
    const fEl = failRefs[g.material_key]
    if (fEl) {
      const failTypes = new Set<string>()
      g.members.forEach((m) => m.final_fail_breakdown.forEach((f) => failTypes.add(f.description)))
      const types = [...failTypes].sort()
      const ex = echarts.getInstanceByDom(fEl)
      if (ex) ex.dispose()
      const c = echarts.init(fEl)
      c.setOption({
        title: { text: '子批次最终 Fail 类型（仍未 Pass）', left: 'center', textStyle: { fontSize: 13 } },
        tooltip: { trigger: 'axis' },
        legend: { data: types, bottom: 0, type: 'scroll' },
        xAxis: { type: 'category', data: memberLabels, axisLabel: { rotate: 20, fontSize: 10 } },
        yAxis: { type: 'value', minInterval: 1 },
        series: types.map((t) => ({
          name: t,
          type: 'bar',
          stack: 'fail',
          data: g.members.map(
            (m) => m.final_fail_breakdown.find((f) => f.description === t)?.count ?? 0,
          ),
        })),
      })
    }
  }
}

async function initFromRoute() {
  await loadCatalog()
  const key = route.params.key as string | undefined
  if (key) {
    selectedKeys.value = [key]
    await applyAnalysis()
  }
}

onMounted(initFromRoute)
watch(() => route.params.key, async (key) => {
  if (key && typeof key === 'string') {
    if (!selectedKeys.value.includes(key)) {
      selectedKeys.value = [key]
    }
    await applyAnalysis()
  }
})
</script>

<style scoped>
.picker-card {
  margin-bottom: 20px;
}
.picker-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}
.picker-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
}
.picker-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.material-title {
  font-weight: 600;
  font-size: 16px;
}
.member-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.member-tag {
  cursor: pointer;
}
</style>

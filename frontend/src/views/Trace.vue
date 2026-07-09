<template>
  <div>
    <h2 class="page-title">芯片追溯</h2>
    <el-form inline>
      <el-form-item label="DieID">
        <el-input v-model="dieId" placeholder="如 0CCE" clearable @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="2DBarCode">
        <el-input v-model="barcode" clearable @keyup.enter="search" />
      </el-form-item>
      <el-button type="primary" @click="search">搜索</el-button>
    </el-form>

    <el-row :gutter="16">
      <el-col :span="10">
        <el-card header="搜索结果（点击打开档案）">
          <el-table
            :data="groupedRows"
            stripe
            v-loading="loading"
            highlight-current-row
            @row-click="openChip"
            size="small"
          >
            <el-table-column prop="die_id" label="DieID" min-width="160" show-overflow-tooltip />
            <el-table-column prop="records" label="记录" width="60" />
            <el-table-column prop="final" label="最终" width="70">
              <template #default="{ row }">
                <el-tag :type="row.final === 'PASS' ? 'success' : 'danger'" size="small">
                  {{ row.final }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="lots" label="LOT" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="14">
        <el-card>
          <template #header>使用说明</template>
          <p>输入 DieID 或 Barcode 搜索，点击行进入<strong>芯片档案</strong>页。</p>
          <p>档案页展示：横向测试时间轴、各轮 Pass/Fail、Log 下钻。</p>
          <p style="color: #909399; font-size: 13px">也可从 LOT 详情 / 物料批次页的芯片列表点击 DieID 跳转。</p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { searchDies, type DieRecord } from '../api'
import { chipPath } from '../utils/material'
import { dieFinalStatus, sortDieRecords } from '../utils/roundOrder'

const router = useRouter()
const dieId = ref('')
const barcode = ref('')
const rows = ref<DieRecord[]>([])
const loading = ref(false)

const groupedRows = computed(() => {
  const map = new Map<string, DieRecord[]>()
  for (const r of rows.value) {
    const list = map.get(r.die_id) || []
    list.push(r)
    map.set(r.die_id, list)
  }
  return [...map.entries()].map(([id, recs]) => {
    const sorted = sortDieRecords(recs)
    const lots = [...new Set(sorted.map((r) => `${r.lot_no}/${r.stage}`))].join(', ')
    return {
      die_id: id,
      records: recs.length,
      final: dieFinalStatus(sorted),
      lots,
    }
  })
})

async function search() {
  if (!dieId.value && !barcode.value) return
  loading.value = true
  try {
    rows.value = await searchDies({
      die_id: dieId.value || undefined,
      barcode: barcode.value || undefined,
    })
  } finally {
    loading.value = false
  }
}

function openChip(row: { die_id: string }) {
  router.push(chipPath(row.die_id))
}
</script>

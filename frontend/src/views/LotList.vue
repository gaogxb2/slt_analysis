<template>
  <div>
    <h2 class="page-title">LOT 列表</h2>
    <el-form inline>
      <el-form-item label="LOT NO.">
        <el-input v-model="filterLot" clearable placeholder="筛选" @clear="load" />
      </el-form-item>
      <el-form-item label="STAGE">
        <el-input v-model="filterStage" clearable @clear="load" />
      </el-form-item>
      <el-button type="primary" @click="load">查询</el-button>
    </el-form>
    <el-table :data="lots" stripe v-loading="loading">
      <el-table-column prop="lot_no" label="LOT NO." />
      <el-table-column prop="stage" label="STAGE" width="80" />
      <el-table-column prop="bin" label="Bin" width="60" />
      <el-table-column prop="traveler_qty" label="Traveler QTY" width="110" />
      <el-table-column prop="input_qty" label="初测投入" width="100" />
      <el-table-column prop="final_pass" label="最终 Pass" width="100" />
      <el-table-column prop="final_fail" label="最终 Fail" width="100" />
      <el-table-column label="最终良率" width="100">
        <template #default="{ row }">{{ row.final_yield_pct }}%</template>
      </el-table-column>
      <el-table-column prop="round_count" label="轮次" width="70" />
      <el-table-column prop="last_report_date" label="最近报告" width="160" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(materialPath(materialKey(row.lot_no)))">
            物料族
          </el-button>
          <el-button link type="primary" @click="router.push(`/lots/${row.lot_no}?stage=${row.stage}`)">
            详情
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getLots, type LotSummary } from '../api'
import { materialKey, materialPath } from '../utils/material'

const router = useRouter()
const lots = ref<LotSummary[]>([])
const loading = ref(false)
const filterLot = ref('')
const filterStage = ref('')

async function load() {
  loading.value = true
  try {
    lots.value = await getLots({
      lot_no: filterLot.value || undefined,
      stage: filterStage.value || undefined,
    })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

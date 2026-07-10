<template>
  <el-drawer
    v-model="visible"
    :title="`芯片 Log — ${detail?.primary_die_id || ''}`"
    size="640px"
    destroy-on-close
  >
    <div v-loading="loading">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small" title="BEGIN 会话头">
          <el-descriptions-item label="LOT">{{ detail.lot_no }}</el-descriptions-item>
          <el-descriptions-item label="STAGE">{{ detail.stage }}</el-descriptions-item>
          <el-descriptions-item label="Site">{{ detail.site }}</el-descriptions-item>
          <el-descriptions-item label="Flow">{{ detail.test_mode }}</el-descriptions-item>
          <el-descriptions-item label="TEST START">{{ detail.test_start }}</el-descriptions-item>
          <el-descriptions-item label="文件">{{ detail.file_path }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin: 16px 0 8px">ONETEST 明细</h4>
        <el-table :data="detail.onetests" size="small" stripe>
          <el-table-column prop="test_txt" label="TEST_TXT" />
          <el-table-column prop="result" label="RESULT" width="90" />
          <el-table-column prop="pf" label="P/F" width="60">
            <template #default="{ row }">
              <el-tag :type="row.pf === 'F' ? 'danger' : 'success'" size="small">{{ row.pf }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="test_time_ms" label="时间(ms)" width="90" />
        </el-table>

        <h4 style="margin: 16px 0 8px">CHIPINFO</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="P/F">
            <el-tag :type="detail.pf === 'F' ? 'danger' : 'success'" size="small">{{ detail.pf }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="SOFT_BIN">{{ detail.soft_bin }}</el-descriptions-item>
          <el-descriptions-item label="TEST_TIME">{{ detail.test_time }}</el-descriptions-item>
          <el-descriptions-item label="Barcode">{{ detail.barcode }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin: 16px 0 8px">DieID 组</h4>
        <el-table :data="detail.die_ids" size="small">
          <el-table-column prop="ordinal" label="#" width="50" />
          <el-table-column prop="die_id_str" label="DIEID_STR" />
          <el-table-column prop="die_id_name" label="NAME" width="120" />
          <el-table-column label="说明" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.ordinal === 1" size="small" type="success">SUM对应</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <template v-if="detail.sum_compare">
          <h4 style="margin: 16px 0 8px">SUM 对比</h4>
          <el-table :data="compareRows" size="small" border>
            <el-table-column prop="field" label="字段" width="100" />
            <el-table-column prop="sum" label="SUM" />
            <el-table-column prop="log" label="Log" />
          </el-table>
        </template>
      </template>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getChipLog, getDieLog, type ChipLogDetail } from '../api'

const props = defineProps<{
  chipLogId?: number | null
  dieRecordId?: number | null
}>()

const visible = defineModel<boolean>({ default: false })
const loading = ref(false)
const detail = ref<ChipLogDetail | null>(null)

const compareRows = computed(() => {
  if (!detail.value?.sum_compare) return []
  const s = detail.value.sum_compare
  const d = detail.value
  return [
    { field: 'booton', sum: s.booton || '—', log: '—' },
    { field: 'Tested', sum: s.tested || '—', log: d.test_time || '—' },
    { field: 'Pass/Fail', sum: s.boot_on, log: d.pf },
    { field: 'Bin', sum: String(s.software_bin), log: String(d.soft_bin) },
    { field: 'Site', sum: String(s.site), log: String(d.site) },
    { field: 'Flow', sum: s.test_mode, log: d.test_mode },
    { field: 'Time', sum: s.test_time, log: d.test_time },
  ]
})

async function load() {
  if (!props.chipLogId && !props.dieRecordId) return
  loading.value = true
  try {
    detail.value = props.chipLogId
      ? await getChipLog(props.chipLogId)
      : await getDieLog(props.dieRecordId!)
  } finally {
    loading.value = false
  }
}

watch(visible, (v) => {
  if (v) load()
})
watch(() => [props.chipLogId, props.dieRecordId], () => {
  if (visible.value) load()
})
</script>

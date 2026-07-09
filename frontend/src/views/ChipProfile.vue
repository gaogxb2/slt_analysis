<template>
  <div v-loading="loading">
    <el-breadcrumb separator="/" style="margin-bottom: 12px">
      <el-breadcrumb-item :to="{ path: '/trace' }">芯片追溯</el-breadcrumb-item>
      <el-breadcrumb-item>{{ displayDieId }}</el-breadcrumb-item>
    </el-breadcrumb>

    <template v-if="timeline.length">
      <el-row :gutter="16" style="margin-bottom: 16px">
        <el-col :span="8">
          <el-card shadow="never">
            <div class="stat-label">DieID</div>
            <div class="stat-value mono">{{ timeline[0].die_id }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never">
            <div class="stat-label">最终状态</div>
            <el-tag :type="finalStatus === 'PASS' ? 'success' : 'danger'" size="large">
              {{ finalStatus }}
            </el-tag>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never">
            <div class="stat-label">物料族</div>
            <div v-if="materialKeys.size">
              <el-button
                v-for="k in materialKeys"
                :key="k"
                link
                type="primary"
                @click="router.push(`/material/${encodeURIComponent(k)}`)"
              >{{ k }}*</el-button>
            </div>
            <span v-else style="color: #909399">—</span>
          </el-card>
        </el-col>
      </el-row>

      <el-card header="测试历程" style="margin-bottom: 16px">
        <div class="timeline-h">
          <div
            v-for="(row, i) in timeline"
            :key="i"
            class="timeline-node"
            :class="{ fail: row.boot_on === 'FAIL' }"
          >
            <div class="node-round">{{ row.stage }} / {{ row.round_key }}</div>
            <div class="node-lot">{{ row.lot_no }}</div>
            <el-tag :type="row.boot_on === 'PASS' ? 'success' : 'danger'" size="small">
              {{ row.boot_on }}
            </el-tag>
            <div class="node-meta">Site {{ row.site }} · EC {{ row.error_code }}</div>
            <el-button
              v-if="row.chip_log_id"
              link
              type="primary"
              size="small"
              @click="openLog(row.chip_log_id, row.id)"
            >Log</el-button>
            <span v-else class="no-log">无 Log</span>
            <div v-if="i < timeline.length - 1" class="arrow">→</div>
          </div>
        </div>
      </el-card>

      <el-card header="各轮明细对比">
        <el-table :data="timeline" stripe size="small">
          <el-table-column prop="lot_no" label="LOT" width="120" />
          <el-table-column prop="stage" label="STAGE" width="70" />
          <el-table-column prop="round_key" label="轮次" width="80" />
          <el-table-column prop="site" label="Site" width="60" />
          <el-table-column prop="boot_on" label="BootOn" width="80" />
          <el-table-column prop="error_code" label="ErrorCode" width="90" />
          <el-table-column prop="software_bin" label="SW Bin" width="80" />
          <el-table-column prop="barcode" label="Barcode" width="130" />
          <el-table-column prop="test_time" label="TestTime" width="80" />
          <el-table-column label="Log" width="80" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.chip_log_id"
                link
                type="primary"
                @click="openLog(row.chip_log_id, row.id)"
              >查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="未找到该 DieID 的测试记录" />

    <ChipLogDrawer v-model="drawerOpen" :chip-log-id="activeLogId" :die-record-id="activeDieId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChipLogDrawer from '../components/ChipLogDrawer.vue'
import { searchDies, type DieRecord } from '../api'
import { materialKey } from '../utils/material'
import { dieFinalStatus, sortDieRecords } from '../utils/roundOrder'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const timeline = ref<DieRecord[]>([])
const drawerOpen = ref(false)
const activeLogId = ref<number | null>(null)
const activeDieId = ref<number | null>(null)

const displayDieId = computed(() => decodeURIComponent(route.params.dieId as string))
const finalStatus = computed(() => dieFinalStatus(timeline.value))
const materialKeys = computed(() => {
  const s = new Set<string>()
  timeline.value.forEach((r) => s.add(materialKey(r.lot_no)))
  return s
})

async function load() {
  const q = decodeURIComponent(route.params.dieId as string)
  if (!q) return
  loading.value = true
  try {
    const rows = await searchDies({ die_id: q })
    const exact = rows.filter(
      (r) => r.die_id.replace(/\s+/g, '').toUpperCase() === q.replace(/\s+/g, '').toUpperCase()
        || r.die_id.toUpperCase().includes(q.toUpperCase()),
    )
    timeline.value = sortDieRecords(exact.length ? exact : rows)
  } finally {
    loading.value = false
  }
}

function openLog(chipLogId?: number, dieId?: number) {
  activeLogId.value = chipLogId ?? null
  activeDieId.value = dieId ?? null
  drawerOpen.value = true
}

onMounted(load)
watch(() => route.params.dieId, load)
</script>

<style scoped>
.stat-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.stat-value { font-size: 15px; font-weight: 600; }
.mono { font-family: monospace; }
.timeline-h {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 8px;
}
.timeline-node {
  position: relative;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 12px;
  min-width: 140px;
  background: #fafafa;
}
.timeline-node.fail {
  border-color: #f56c6c;
  background: #fef0f0;
}
.node-round { font-weight: 600; font-size: 13px; }
.node-lot { font-size: 12px; color: #606266; margin: 4px 0; }
.node-meta { font-size: 11px; color: #909399; margin-top: 4px; }
.no-log { font-size: 12px; color: #c0c4cc; }
.arrow {
  position: absolute;
  right: -18px;
  top: 50%;
  transform: translateY(-50%);
  color: #909399;
  font-size: 18px;
}
</style>

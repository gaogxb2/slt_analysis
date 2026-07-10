<template>
  <div>
    <h2 class="page-title">数据导入</h2>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card header="上传 SUM 文件">
          <el-upload
            drag
            multiple
            :auto-upload="false"
            :on-change="onFileChange"
            accept=".SUM,.sum,.log"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div>拖拽或点击选择 .SUM / .log 文件</div>
          </el-upload>
          <el-button type="primary" style="margin-top: 12px" :loading="uploading" @click="doUpload">
            开始上传
          </el-button>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="扫描目录">
          <p>递归扫描项目 logs 目录下的所有 .SUM 文件</p>
          <el-button type="primary" :loading="scanning" @click="doScan">扫描 SUM</el-button>
          <p style="margin-top: 16px">递归扫描项目 logs 目录下的所有 .log 文件</p>
          <el-button type="primary" :loading="scanningLogs" @click="doScanLogs">扫描 Log</el-button>
          <el-alert v-if="scanResult" :title="`SUM 成功 ${scanResult.ok?.length || 0} 个`" type="success" style="margin-top: 12px" />
          <el-alert v-if="logScanResult" :title="`Log 成功 ${logScanResult.ok?.length || 0} 个`" type="success" style="margin-top: 8px" />
          <el-alert
            v-for="(e, i) in scanResult?.errors || []"
            :key="'s' + i"
            :title="`${e.file}: ${e.error}`"
            type="warning"
            style="margin-top: 8px"
          />
          <el-alert
            v-for="(e, i) in logScanResult?.errors || []"
            :key="'l' + i"
            :title="`${e.file}: ${e.error}`"
            type="warning"
            style="margin-top: 8px"
          />
        </el-card>
      </el-col>
    </el-row>
    <el-card header="数据库维护" style="margin-top: 16px">
      <p style="color: #606266; margin: 0 0 12px">
        清空 SQLite 中全部 LOT、SUM、Log、芯片记录及导入日志。此操作不可恢复，清空后需重新扫描 logs 入库。
      </p>
      <el-button type="danger" :loading="clearing" @click="confirmClearAll">
        清空全部数据
      </el-button>
    </el-card>

    <el-card header="导入日志" style="margin-top: 16px">
      <el-table :data="logs" size="small">
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column prop="filename" label="文件" />
        <el-table-column prop="status" label="状态" width="80" />
        <el-table-column prop="message" label="消息" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { uploadFiles, scanTestdata, scanTestlogs, getImportLogs, clearAllDatabase } from '../api'

const pendingFiles = ref<File[]>([])
const uploading = ref(false)
const scanning = ref(false)
const scanningLogs = ref(false)
const clearing = ref(false)
const scanResult = ref<{ ok: string[]; errors: Array<{ file: string; error: string }> } | null>(null)
const logScanResult = ref<{ ok: string[]; errors: Array<{ file: string; error: string }> } | null>(null)
const logs = ref<Array<Record<string, unknown>>>([])

function onFileChange(_: UploadFile, fileList: UploadFile[]) {
  pendingFiles.value = fileList.map((f) => f.raw!).filter(Boolean)
}

async function doUpload() {
  if (!pendingFiles.value.length) return
  uploading.value = true
  try {
    await uploadFiles(pendingFiles.value)
    pendingFiles.value = []
    await loadLogs()
  } finally {
    uploading.value = false
  }
}

async function doScan() {
  scanning.value = true
  try {
    scanResult.value = await scanTestdata()
    await loadLogs()
  } finally {
    scanning.value = false
  }
}

async function doScanLogs() {
  scanningLogs.value = true
  try {
    logScanResult.value = await scanTestlogs()
    await loadLogs()
  } finally {
    scanningLogs.value = false
  }
}

async function loadLogs() {
  logs.value = await getImportLogs()
}

async function confirmClearAll() {
  try {
    await ElMessageBox.confirm(
      '将永久删除数据库中的全部 LOT、轮次、芯片、Log 及导入日志，且无法恢复。确定继续？',
      '清空全部数据',
      {
        type: 'warning',
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }

  clearing.value = true
  try {
    const result = await clearAllDatabase()
    scanResult.value = null
    logScanResult.value = null
    await loadLogs()
    ElMessage.success(result.message || '数据库已清空')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '清空失败'
    ElMessage.error(msg)
  } finally {
    clearing.value = false
  }
}

onMounted(loadLogs)
</script>

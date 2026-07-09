<template>
  <el-button link type="primary" @click.stop="go">{{ dieId }}</el-button>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { chipPath } from '../utils/material'

const props = defineProps<{ dieId: string }>()
const router = useRouter()

function go() {
  router.push(chipPath(props.dieId))
}
</script>

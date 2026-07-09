<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">SLT 统计</div>
      <el-menu :default-active="activeMenu" router>
        <el-menu-item index="/">
          <el-icon><Odometer /></el-icon>
          <span>总览</span>
        </el-menu-item>
        <el-menu-item index="/material">
          <el-icon><Box /></el-icon>
          <span>物料批次</span>
        </el-menu-item>
        <el-menu-item index="/trace">
          <el-icon><Search /></el-icon>
          <span>芯片追溯</span>
        </el-menu-item>
        <el-menu-item index="/lots">
          <el-icon><List /></el-icon>
          <span>LOT 列表</span>
        </el-menu-item>
        <el-menu-item index="/import">
          <el-icon><Upload /></el-icon>
          <span>数据导入</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => {
  if (route.path.startsWith('/material')) return '/material'
  if (route.path.startsWith('/chips') || route.path.startsWith('/trace')) return '/trace'
  if (route.path.startsWith('/lots')) return '/lots'
  return route.path
})
</script>

<style scoped>
.layout { height: 100%; }
.aside {
  background: #1d1e1f;
  color: #fff;
}
.logo {
  padding: 20px 16px;
  font-size: 18px;
  font-weight: 700;
  border-bottom: 1px solid #333;
}
.aside :deep(.el-menu) {
  border-right: none;
  background: #1d1e1f;
}
.aside :deep(.el-menu-item) {
  color: #ccc;
}
.aside :deep(.el-menu-item.is-active) {
  background: #409eff;
  color: #fff;
}
.main {
  background: #f5f7fa;
  padding: 20px;
}
</style>

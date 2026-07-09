import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('../views/Dashboard.vue') },
    { path: '/material', name: 'material', component: () => import('../views/MaterialOverview.vue') },
    { path: '/material/:key', name: 'material-detail', component: () => import('../views/MaterialOverview.vue') },
    { path: '/trace', name: 'trace', component: () => import('../views/Trace.vue') },
    { path: '/chips/:dieId', name: 'chip-profile', component: () => import('../views/ChipProfile.vue') },
    { path: '/lots', name: 'lots', component: () => import('../views/LotList.vue') },
    { path: '/lots/:lotNo/reconcile', name: 'reconcile', component: () => import('../views/Reconcile.vue') },
    { path: '/lots/:lotNo', name: 'lot-detail', component: () => import('../views/LotDetail.vue') },
    { path: '/analysis', redirect: '/lots' },
    { path: '/import', name: 'import', component: () => import('../views/Import.vue') },
  ],
})

export default router

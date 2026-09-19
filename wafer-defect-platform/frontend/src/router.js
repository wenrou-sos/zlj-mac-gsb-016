import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import WaferMapView from './views/WaferMapView.vue'
import ImportView from './views/ImportView.vue'
import YieldCompare from './views/YieldCompare.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard, meta: { title: '仪表盘' } },
    { path: '/map', name: 'wafermap', component: WaferMapView, meta: { title: '晶圆图谱' } },
    { path: '/import', name: 'import', component: ImportView, meta: { title: '数据导入' } },
    { path: '/yield', name: 'yield', component: YieldCompare, meta: { title: '良率对比' } },
  ]
})

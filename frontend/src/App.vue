<template>
  <div>
    <header class="app-header">
      <span class="logo">🔬</span>
      <div>
        <h1>晶圆缺陷图谱分析平台</h1>
        <div class="sub">Wafer Defect Map Analysis · 点位导入 / 空间聚集识别 / 批次良率对比</div>
      </div>
      <span class="health" :class="{ bad: !apiOk }">
        {{ apiOk ? '● 后端在线' : '● 后端离线' }}
      </span>
    </header>

    <nav class="tabs">
      <button :class="{ active: tab === 'map' }" @click="switchTab('map')">晶圆图谱</button>
      <button :class="{ active: tab === 'compare' }" @click="switchTab('compare')">批次良率对比</button>
      <button :class="{ active: tab === 'import' }" @click="switchTab('import')">数据导入</button>
    </nav>

    <main class="content">
      <MapView v-if="tab === 'map'" ref="mapView" />
      <CompareView v-else-if="tab === 'compare'"
                   :refresh-key="refreshKey"
                   @open-wafer="openWafer" />
      <ImportView v-else @imported="onImported" />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from './api.js'
import MapView from './components/MapView.vue'
import CompareView from './components/CompareView.vue'
import ImportView from './components/ImportView.vue'

const tab = ref('map')
const apiOk = ref(false)
const refreshKey = ref(0)
const mapView = ref(null)

async function checkHealth() {
  try {
    await api.health()
    apiOk.value = true
  } catch {
    apiOk.value = false
  }
}

function switchTab(t) {
  tab.value = t
  if (t === 'compare') refreshKey.value++
  if (t === 'map') mapView.value?.reload()
}

async function onImported(batchId) {
  refreshKey.value++
  await checkHealth()
  if (tab.value === 'map') await mapView.value?.reload()
}

async function openWafer(waferId) {
  tab.value = 'map'
  await mapView.value?.reload()
  await mapView.value?.loadWafer(waferId)
}

onMounted(() => {
  checkHealth()
  setInterval(checkHealth, 10000)
})
</script>

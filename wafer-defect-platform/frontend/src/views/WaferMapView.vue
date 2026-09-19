<template>
  <div>
    <div class="card controls">
      <label class="field">批次
        <select v-model="selectedLot" @change="onLotChange">
          <option v-for="l in lots" :key="l.id" :value="l.id">{{ l.name }}</option>
        </select>
      </label>
      <label class="field">晶圆
        <select v-model="selectedWafer" @change="loadMap">
          <option v-for="w in wafers" :key="w.id" :value="w.id">
            #{{ w.wafer_number }}（良率 {{ pct(w.yield) }}）
          </option>
        </select>
      </label>
      <label class="field">邻域半径 ε
        <input type="number" v-model.number="eps" min="0.5" max="20" step="0.5" />
      </label>
      <label class="field">最小样本数
        <input type="number" v-model.number="minSamples" min="2" max="50" />
      </label>
      <button class="btn" @click="analyze" :disabled="!mapData">识别聚集</button>
    </div>

    <div v-if="mapData" class="map-layout">
      <div class="card">
        <h3>
          {{ mapData.lot_name }} / 晶圆 #{{ mapData.wafer_number }}
          <span class="stat">良率 {{ pct(mapData.yield) }} ·
            失效管芯 {{ mapData.defective_dies }}/{{ mapData.total_dies }} ·
            缺陷 {{ mapData.defect_count }} 个</span>
        </h3>
        <div ref="mapEl" class="wafer-chart"></div>
      </div>
      <div class="card cluster-panel">
        <h3>聚集分析
          <span v-if="clusterData" class="stat">
            {{ clusterData.cluster_count }} 个簇 · {{ clusterData.noise_count }} 个散点
          </span>
        </h3>
        <div v-if="!clusterData" class="hint">点击「识别聚集」运行 DBSCAN 密度聚类分析</div>
        <div v-else-if="!clusterData.clusters.length" class="hint">未发现明显聚集，缺陷呈随机分布</div>
        <div v-for="(c, i) in clusterData?.clusters || []" :key="c.id" class="cluster-item">
          <span class="dot" :style="{ background: clusterColors[i % clusterColors.length] }"></span>
          <div>
            <div class="cluster-title">
              {{ c.pattern_label }}
              <span class="badge">{{ c.size }} 点</span>
              <span class="badge type">{{ c.dominant_type }}</span>
            </div>
            <div class="cluster-sub">
              中心 ({{ c.centroid.x }}, {{ c.centroid.y }}) · 半径 {{ c.radius }} ·
              范围 x[{{ c.bbox.x_min }},{{ c.bbox.x_max }}] y[{{ c.bbox.y_min }},{{ c.bbox.y_max }}]
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="card hint" style="margin-top:20px">
      {{ lots.length ? '请选择批次与晶圆' : '暂无数据，请先到「数据导入」页导入或生成演示数据' }}
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { api, pct } from '../api'

const CLUSTER_PALETTE = ['#e53935', '#8e24aa', '#3949ab', '#00897b', '#f4511e', '#6d4c41']
const clusterColors = CLUSTER_PALETTE

const lots = ref([])
const wafers = ref([])
const selectedLot = ref(null)
const selectedWafer = ref(null)
const eps = ref(3.0)
const minSamples = ref(4)
const mapData = ref(null)
const clusterData = ref(null)
const mapEl = ref(null)
let chart = null

function circlePoints(cx, cy, r, n = 96) {
  const pts = []
  for (let i = 0; i <= n; i++) {
    const t = (i / n) * Math.PI * 2
    pts.push([cx + r * Math.cos(t), cy + r * Math.sin(t)])
  }
  return pts
}

function render() {
  const d = mapData.value
  const rows = d.die_rows, cols = d.die_cols
  const dieMap = new Map(d.dies.map(x => [`${x.x},${x.y}`, x.defect_count]))

  // 全部管芯热力图：0=良品，≥1=失效
  const dieData = []
  for (let y = 0; y < rows; y++)
    for (let x = 0; x < cols; x++)
      dieData.push([x, y, dieMap.get(`${x},${y}`) || 0])

  // 缺陷散点（按类型分组以支持图例），同管芯多缺陷加确定性抖动
  const byType = {}
  d.defects.forEach((def, i) => {
    const jx = ((i * 37) % 10 - 4.5) / 22, jy = ((i * 53) % 10 - 4.5) / 22
    ;(byType[def.code] ||= { name: `${def.name}`, color: def.color, data: [] })
      .data.push([def.x + jx, def.y + jy])
  })

  const cx = (cols - 1) / 2, cy = (rows - 1) / 2, r = Math.min(rows, cols) / 2

  const series = [
    { name: '管芯', type: 'heatmap', data: dieData, silent: true,
      itemStyle: { borderColor: '#fff', borderWidth: 0.5 } },
    // 晶圆边界圆
    { name: '边界', type: 'line', data: circlePoints(cx, cy, r), silent: true,
      symbol: 'none', lineStyle: { color: '#455a64', width: 2 }, z: 5, tooltip: { show: false } },
    // 缺陷散点
    ...Object.entries(byType).map(([code, t]) => ({
      name: t.name, type: 'scatter', symbolSize: 7, data: t.data, z: 10,
      itemStyle: { color: t.color, borderColor: '#fff', borderWidth: 0.5 },
    })),
  ]

  // 聚集圈选（虚线圆 + 标签）
  ;(clusterData.value?.clusters || []).forEach((c, i) => {
    const color = CLUSTER_PALETTE[i % CLUSTER_PALETTE.length]
    series.push({
      name: `簇${i + 1}`, type: 'line', silent: true, symbol: 'none', z: 8,
      data: circlePoints(c.centroid.x, c.centroid.y, c.radius + 0.8),
      lineStyle: { color, width: 2, type: 'dashed' },
      label: { show: true, position: 'end', formatter: `${c.pattern_label}(${c.size})`,
               color, fontWeight: 600, fontSize: 11 },
      tooltip: { show: false },
    })
  })

  const option = {
    tooltip: {
      formatter: p => p.seriesType === 'heatmap'
        ? `管芯 (${p.data[0]}, ${p.data[1]})<br/>缺陷数：${p.data[2]}`
        : `${p.seriesName}<br/>位置 (${p.data[0].toFixed(1)}, ${p.data[1].toFixed(1)})`,
    },
    legend: { bottom: 0, itemWidth: 12, itemHeight: 12, textStyle: { fontSize: 12 } },
    grid: { left: 40, right: 30, top: 20, bottom: 50 },
    xAxis: { type: 'value', min: -0.5, max: cols - 0.5, aspectScale: 1,
             splitLine: { show: false }, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', min: -0.5, max: rows - 0.5, inverse: true, aspectScale: 1,
             splitLine: { show: false }, axisLabel: { fontSize: 10 } },
    visualMap: {
      type: 'piecewise', dimension: 2, seriesIndex: 0, orient: 'horizontal',
      left: 'center', top: 0, itemWidth: 12, itemHeight: 12, textStyle: { fontSize: 11 },
      pieces: [
        { value: 0, label: '良品', color: '#a5d6a7' },
        { value: 1, label: '1缺陷', color: '#fff176' },
        { value: 2, label: '2缺陷', color: '#ffb74d' },
        { min: 3, label: '≥3缺陷', color: '#e57373' },
      ],
    },
    series,
  }
  if (!chart) chart = echarts.init(mapEl.value)
  chart.setOption(option, true)
  chart.resize()
}

async function onLotChange() {
  wafers.value = await api.wafers(selectedLot.value)
  selectedWafer.value = wafers.value[0]?.id ?? null
  clusterData.value = null
  if (selectedWafer.value) await loadMap()
}

async function loadMap() {
  if (!selectedWafer.value) return
  clusterData.value = null
  mapData.value = await api.waferMap(selectedWafer.value)
  await nextTick()
  render()
}

async function analyze() {
  clusterData.value = await api.clusters(selectedWafer.value, eps.value, minSamples.value)
  render()  // 重绘以叠加聚集圈
}

onMounted(async () => {
  lots.value = await api.lots()
  if (lots.value.length) {
    selectedLot.value = lots.value[0].id
    await onLotChange()
  }
  window.addEventListener('resize', () => chart?.resize())
})
</script>

<style scoped>
.controls { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 20px; }
.controls .field { min-width: 140px; }
.map-layout { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }
.wafer-chart { height: 560px; }
.stat { font-size: 12px; color: #90a4ae; font-weight: 400; margin-left: 8px; }
.hint { color: #90a4ae; font-size: 13px; padding: 12px 0; }
.cluster-panel { max-height: 620px; overflow-y: auto; }
.cluster-item { display: flex; gap: 10px; padding: 10px 0; border-bottom: 1px solid #eceff1; }
.dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
.cluster-title { font-size: 14px; font-weight: 600; display: flex; gap: 6px; align-items: center; }
.badge { background: #eceff1; color: #546e7a; font-size: 11px; padding: 1px 8px;
         border-radius: 10px; font-weight: 400; }
.badge.type { background: #e3f2fd; color: #1565c0; }
.cluster-sub { font-size: 12px; color: #90a4ae; margin-top: 3px; }
</style>

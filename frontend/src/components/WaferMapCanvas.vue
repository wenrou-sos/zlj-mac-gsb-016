<template>
  <div class="map-wrap">
    <canvas ref="canvas" :width="size" :height="size"
            @mousemove="onMove" @mouseleave="tip = null"></canvas>
    <div v-if="tip" class="tooltip" :style="{ left: tip.x + 14 + 'px', top: tip.y + 14 + 'px' }">
      <div><b>{{ tip.point.defect_type === 'GOOD' ? '正常点' : tip.point.defect_type }}</b></div>
      <div class="muted">({{ tip.point.x_mm }}, {{ tip.point.y_mm }}) mm</div>
      <div v-if="clusterOf(tip.point.id)" class="muted">
        所属缺陷簇 #{{ clusterOf(tip.point.id) }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { defectColor } from '../api.js'

const props = defineProps({
  points: { type: Array, required: true },
  analysis: { type: Object, required: true },
  diameterMm: { type: Number, default: 300 }
})

const size = 640
const canvas = ref(null)
const tip = ref(null)

// 缺陷点 id -> 簇 映射
const clusterMap = computed(() => {
  const m = new Map()
  for (const c of props.analysis.clusters || []) {
    for (const id of c.point_ids || []) m.set(id, c.cluster_id)
  }
  return m
})
function clusterOf(id) {
  return clusterMap.value.has(id) ? clusterMap.value.get(id) : null
}

// 推断 die 边长：坐标差值的最小正公约数（用最小相邻间距近似）
const dieSizeMm = computed(() => {
  const xs = [...new Set(props.points.map(p => p.x_mm))].sort((a, b) => a - b)
  let min = Infinity
  for (let i = 1; i < xs.length; i++) min = Math.min(min, xs[i] - xs[i - 1])
  if (!isFinite(min) || min <= 0) return 10
  return min
})

function draw() {
  const cv = canvas.value
  if (!cv) return
  const ctx = cv.getContext('2d')
  const radiusMm = props.diameterMm / 2
  const margin = 26
  const scale = (size / 2 - margin) / radiusMm
  const cx = size / 2
  const cy = size / 2
  const diePx = Math.max(dieSizeMm.value * scale - 0.6, 2)

  ctx.clearRect(0, 0, size, size)

  // 晶圆基底
  ctx.beginPath()
  ctx.arc(cx, cy, radiusMm * scale, 0, Math.PI * 2)
  ctx.fillStyle = '#101a2b'
  ctx.fill()
  ctx.lineWidth = 2
  ctx.strokeStyle = '#3d5278'
  ctx.stroke()

  // 参考环（50% / 82% 半径）
  for (const [r, label] of [[0.5, '50%'], [0.82, '82%']]) {
    ctx.beginPath()
    ctx.arc(cx, cy, radiusMm * scale * r, 0, Math.PI * 2)
    ctx.strokeStyle = 'rgba(255,255,255,0.07)'
    ctx.lineWidth = 1
    ctx.stroke()
  }

  // 晶圆平边定位标记（底部 notch）
  ctx.beginPath()
  ctx.moveTo(cx - 10, cy + radiusMm * scale - 2)
  ctx.lineTo(cx + 10, cy + radiusMm * scale - 2)
  ctx.strokeStyle = '#0f1623'
  ctx.lineWidth = 4
  ctx.stroke()

  // 画 die
  for (const p of props.points) {
    const px = cx + p.x_mm * scale
    const py = cy - p.y_mm * scale
    if (p.is_defect) {
      ctx.fillStyle = defectColor(p.defect_type)
      ctx.fillRect(px - diePx / 2, py - diePx / 2, diePx, diePx)
    } else {
      ctx.fillStyle = '#1d2c45'
      ctx.fillRect(px - diePx / 2, py - diePx / 2, diePx, diePx)
    }
  }

  // 异常簇：高亮圆圈
  for (const c of props.analysis.clusters || []) {
    if (!c.is_anomaly) continue
    const px = cx + c.center_x * scale
    const py = cy - c.center_y * scale
    const r = Math.max(c.spread_mm * scale + diePx, 14)
    ctx.beginPath()
    ctx.arc(px, py, r, 0, Math.PI * 2)
    ctx.strokeStyle = c.severity === 'high'
      ? 'rgba(255,93,108,0.95)' : 'rgba(255,176,32,0.9)'
    ctx.lineWidth = c.severity === 'high' ? 2.5 : 2
    ctx.setLineDash([6, 4])
    ctx.stroke()
    ctx.setLineDash([])
    // 簇编号标签
    ctx.fillStyle = c.severity === 'high' ? '#ff5d6c' : '#ffb020'
    ctx.font = 'bold 11px sans-serif'
    ctx.fillText(`#${c.cluster_id}`, px + r + 3, py - r + 4)
  }

  // 坐标轴
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'
  ctx.lineWidth = 1
  ctx.beginPath(); ctx.moveTo(cx - radiusMm * scale, cy); ctx.lineTo(cx + radiusMm * scale, cy); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(cx, cy - radiusMm * scale); ctx.lineTo(cx, cy + radiusMm * scale); ctx.stroke()
}

function onMove(e) {
  const rect = canvas.value.getBoundingClientRect()
  const mx = (e.clientX - rect.left) * (size / rect.width)
  const my = (e.clientY - rect.top) * (size / rect.height)
  const radiusMm = props.diameterMm / 2
  const margin = 26
  const scale = (size / 2 - margin) / radiusMm
  const wx = (mx - size / 2) / scale
  const wy = -(my - size / 2) / scale
  let best = null
  let bestD = Infinity
  const hit = dieSizeMm.value / 2 + 1
  for (const p of props.points) {
    const d = Math.max(Math.abs(p.x_mm - wx), Math.abs(p.y_mm - wy))
    if (d < hit && d < bestD) { best = p; bestD = d }
  }
  if (best) {
    tip.value = { x: e.clientX, y: e.clientY, point: best }
  } else {
    tip.value = null
  }
}

onMounted(draw)
watch(() => [props.points, props.analysis], draw, { deep: false })
</script>

<style scoped>
.map-wrap { display: flex; justify-content: center; }
canvas {
  width: 100%;
  max-width: 640px;
  height: auto;
  cursor: crosshair;
}
</style>

<template>
  <div>
    <div class="layout">
      <!-- 左：批次/晶圆列表 -->
      <div class="panel">
        <h2>批次 / 晶圆</h2>
        <div v-if="!batches.length" class="muted">
          暂无数据，请先到「数据导入」页导入 CSV/JSON 或载入演示数据。
        </div>
        <div v-for="b in batches" :key="b.id" style="margin-bottom: 14px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <b style="font-size:13px;">{{ b.name }}</b>
            <button class="btn danger" style="padding:2px 8px; font-size:11px;"
                    @click="removeBatch(b.id)">删除</button>
          </div>
          <div class="muted" style="font-size:11px; margin-bottom:6px;">
            {{ b.product || '—' }} · {{ b.wafer_count }} 片 · 良率 {{ pct(b.yield_rate) }}
          </div>
          <div v-for="w in waferMap.get(b.id) || []" :key="w.id"
               class="list-item"
               :class="{ active: current && current.wafer.id === w.id }"
               @click="loadWafer(w.id)">
            <div>
              <div class="name">{{ w.name }}</div>
              <div class="meta">{{ w.point_count }} 点 · 缺陷 {{ w.defect_count }}</div>
            </div>
            <span class="badge" :class="yieldClass(w.yield_rate) === 'bad' ? 'high'
              : yieldClass(w.yield_rate) === 'warn' ? 'medium' : 'low'">
              {{ pct(w.yield_rate) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 右：图谱与分析 -->
      <div v-if="current" class="panel">
        <div style="display:flex; justify-content:space-between; align-items:baseline;">
          <h2>
            {{ current.wafer.name }}
            <span class="muted" style="font-weight:400;">
              · ⌀{{ current.wafer.diameter_mm }}mm · {{ current.wafer.point_count }} 检测点
            </span>
          </h2>
          <span class="badge" :class="current.analysis.overall_severity">
            {{ current.analysis.has_anomaly ? '检测到异常' : '状态正常' }}
          </span>
        </div>

        <div class="layout-3" style="grid-template-columns:repeat(4,1fr); margin-bottom:8px;">
          <div class="stat"><div class="k">良率</div>
            <div class="v" :class="yieldClass(current.analysis.yield_rate)">
              {{ pct(current.analysis.yield_rate) }}
            </div>
          </div>
          <div class="stat"><div class="k">缺陷数</div>
            <div class="v">{{ current.analysis.defect_count }}</div>
          </div>
          <div class="stat"><div class="k">缺陷簇</div>
            <div class="v">{{ current.analysis.cluster_count }}</div>
          </div>
          <div class="stat"><div class="k">异常簇</div>
            <div class="v" :class="current.analysis.anomaly_cluster_count ? 'bad' : ''">
              {{ current.analysis.anomaly_cluster_count }}
            </div>
          </div>
        </div>

        <div class="layout" style="grid-template-columns: minmax(0, 1.35fr) minmax(280px, 1fr);">
          <WaferMapCanvas :points="current.points"
                          :analysis="current.analysis"
                          :diameter-mm="current.wafer.diameter_mm" />
          <div>
            <h2 style="font-size:13px;">空间模式识别</h2>
            <div v-for="(p, i) in current.analysis.patterns" :key="i"
                 class="pattern-card" :class="p.severity">
              <div class="t">
                <span>{{ p.name }}</span>
                <span class="badge" :class="p.severity">{{ severityText(p.severity) }}</span>
              </div>
              <div class="d">{{ p.description }}</div>
            </div>

            <h2 style="font-size:13px; margin-top:14px;">缺陷类型分布</h2>
            <table>
              <tr v-for="t in current.analysis.defect_type_counts" :key="t.defect_type">
                <td>
                  <span class="legend">
                    <span class="swatch" :style="{background: defectColor(t.defect_type)}"></span>
                    {{ defectLabel(t.defect_type) }}
                  </span>
                </td>
                <td style="text-align:right;">{{ t.count }}</td>
              </tr>
            </table>
          </div>
        </div>

        <h2 style="font-size:13px; margin-top:18px;">缺陷簇明细（DBSCAN, eps={{ current.analysis.params.eps }}mm）</h2>
        <table v-if="current.analysis.clusters.length">
          <thead>
            <tr>
              <th>#</th><th>模式</th><th>点数</th><th>中心 (mm)</th>
              <th>相对密度</th><th>线性比</th><th>主要缺陷</th><th>等级</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in current.analysis.clusters" :key="c.cluster_id">
              <td>{{ c.cluster_id }}</td>
              <td>{{ patternText(c.pattern) }}</td>
              <td>{{ c.size }}</td>
              <td class="muted">({{ c.center_x }}, {{ c.center_y }})</td>
              <td>{{ c.relative_density }}x</td>
              <td>{{ c.linear_ratio ?? '—' }}</td>
              <td class="muted">
                {{ c.defect_types.slice(0, 2).map(t => `${t.defect_type}×${t.count}`).join('，') }}
              </td>
              <td><span class="badge" :class="c.severity">{{ severityText(c.severity) }}</span></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="muted">缺陷点稀疏，未形成任何密度簇。</div>
      </div>

      <div v-else class="panel" style="display:flex; align-items:center; justify-content:center;
                                      min-height:420px; color:var(--text-dim);">
        ← 请从左侧选择一片晶圆查看缺陷分布图
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api, pct, yieldClass, defectColor, DEFECT_TYPE_LABELS, PATTERN_LABELS } from '../api.js'
import WaferMapCanvas from './WaferMapCanvas.vue'

const batches = ref([])
const waferMap = ref(new Map())
const current = ref(null)

async function loadAll() {
  batches.value = await api.listBatches()
  const wm = new Map()
  await Promise.all(batches.value.map(async b => {
    wm.set(b.id, await api.listWafers(b.id))
  }))
  waferMap.value = wm
}

async function loadWafer(id) {
  current.value = await api.waferMap(id)
}

async function removeBatch(id) {
  if (!confirm('确定删除该批次及其全部晶圆、点位数据？')) return
  await api.deleteBatch(id)
  if (current.value && waferMap.value.get(id)?.some(w => w.id === current.value.wafer.id)) {
    current.value = null
  }
  await loadAll()
}

function defectLabel(t) { return DEFECT_TYPE_LABELS[t] || t }
function patternText(c) { return PATTERN_LABELS[c] || c }
function severityText(s) { return { high: '高', medium: '中', low: '低' }[s] || s }

onMounted(loadAll)
defineExpose({ reload: loadAll, loadFirstWafer: async () => {
  await loadAll()
  const first = waferMap.value.get(batches.value[0]?.id)?.[0]
  if (first) await loadWafer(first.id)
} })
</script>

<template>
  <div v-if="loading" class="panel"><span class="spinner"></span> <span class="muted">正在计算各批次分析结果…</span></div>

  <div v-else-if="!items.length" class="panel muted">
    暂无可对比的批次，请先导入数据。
  </div>

  <template v-else>
    <!-- 良率对比柱状图 -->
    <div class="panel" style="margin-bottom:18px;">
      <h2>批次良率对比</h2>
      <div style="display:flex; align-items:flex-end; gap:28px; height:260px; padding: 10px 20px 0;">
        <div v-for="b in items" :key="b.batch_id"
             style="flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%;">
          <div class="muted" style="font-size:12px; margin-bottom:6px;">
            平均 {{ pct(b.avg_wafer_yield, 2) }}
          </div>
          <div style="width:100%; max-width:90px; display:flex; gap:4px; align-items:flex-end; height:190px;">
            <div v-for="w in b.wafers" :key="w.id"
                 :title="`${w.name}: ${pct(w.yield_rate)}`"
                 :style="{
                   height: barHeight(w.yield_rate),
                   background: w.has_anomaly
                     ? (w.overall_severity === 'high' ? '#ff5d6c' : '#ffb020')
                     : '#39d98a'
                 }"
                 style="flex:1; border-radius:4px 4px 0 0; min-height:3px; transition:height .3s;"></div>
          </div>
          <div style="font-size:12px; margin-top:8px; font-weight:600;">{{ b.batch_name }}</div>
          <div class="muted" style="font-size:11px;">σ={{ pct(b.yield_stddev, 2) }}</div>
        </div>
      </div>
      <div style="display:flex; gap:18px; padding: 10px 20px; border-top:1px solid var(--border); margin-top:10px;">
        <span class="item"><span class="swatch" style="background:#39d98a"></span> 正常晶圆</span>
        <span class="item"><span class="swatch" style="background:#ffb020"></span> 中等异常</span>
        <span class="item"><span class="swatch" style="background:#ff5d6c"></span> 严重异常</span>
      </div>
    </div>

    <!-- 批次汇总表 -->
    <div class="panel" style="margin-bottom:18px;">
      <h2>批次汇总</h2>
      <table>
        <thead>
          <tr>
            <th>批次</th><th>产品</th><th>晶圆数</th><th>检测点</th><th>缺陷数</th>
            <th>整体良率</th><th>片均良率</th><th>片间波动 σ</th>
            <th>异常晶圆</th><th>等级</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in items" :key="b.batch_id">
            <td><b>{{ b.batch_name }}</b></td>
            <td class="muted">{{ b.product || '—' }}</td>
            <td>{{ b.wafer_count }}</td>
            <td>{{ b.point_count }}</td>
            <td>{{ b.defect_count }}</td>
            <td>
              <div style="display:flex; align-items:center; gap:8px;">
                <div class="bar-track" style="width:90px;">
                  <div class="bar-fill" :class="yieldClass(b.yield_rate)"
                       :style="{ width: (b.yield_rate * 100) + '%' }"></div>
                </div>
                <b :class="'stat-label-' + yieldClass(b.yield_rate)">{{ pct(b.yield_rate) }}</b>
              </div>
            </td>
            <td>{{ pct(b.avg_wafer_yield) }}</td>
            <td>{{ pct(b.yield_stddev) }}</td>
            <td>{{ b.anomaly_wafer_count }} / {{ b.wafer_count }}</td>
            <td><span class="badge" :class="b.severity">{{ severityText(b.severity) }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 各晶圆明细 -->
    <div class="panel">
      <h2>晶圆级明细（点击行查看图谱）</h2>
      <table>
        <thead>
          <tr>
            <th>批次</th><th>晶圆</th><th>检测点</th><th>缺陷数</th>
            <th>良率</th><th>空间模式</th><th>等级</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in flatWafers" :key="row.wafer.id" class="clickable"
              @click="$emit('open-wafer', row.wafer.id)">
            <td class="muted">{{ row.batchName }}</td>
            <td><b>{{ row.wafer.name }}</b></td>
            <td>{{ row.wafer.point_count }}</td>
            <td>{{ row.wafer.defect_count }}</td>
            <td><span :style="{color: yieldColor(row.wafer.yield_rate)}">
              {{ pct(row.wafer.yield_rate) }}
            </span></td>
            <td>
              <span v-for="code in row.wafer.patterns" :key="code"
                    class="badge low" style="margin-right:4px; background:rgba(77,163,255,.15); color:var(--accent);">
                {{ PATTERN_LABELS[code] || code }}
              </span>
            </td>
            <td>
              <span class="badge" :class="row.wafer.overall_severity">
                {{ severityText(row.wafer.overall_severity) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api, pct, yieldClass, PATTERN_LABELS } from '../api.js'

const props = defineProps({ refreshKey: Number })
defineEmits(['open-wafer'])

const items = ref([])
const loading = ref(true)

const YIELD_MIN = 0.8
function barHeight(y) {
  const h = Math.max(0, Math.min(1, (y - YIELD_MIN) / (1 - YIELD_MIN)))
  return `${h * 100}%`
}
function severityText(s) { return { high: '严重', medium: '中等', low: '正常' }[s] || s }
function yieldColor(y) {
  return y >= 0.97 ? '#39d98a' : y >= 0.93 ? '#ffb020' : '#ff5d6c'
}

const flatWafers = computed(() =>
  items.value.flatMap(b =>
    b.wafers.map(w => ({ batchName: b.batch_name, wafer: w }))
  )
)

async function load() {
  loading.value = true
  try {
    items.value = await api.compare()
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => props.refreshKey, load)
</script>

<style scoped>
.item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-dim); }
.swatch { width: 12px; height: 12px; border-radius: 3px; }
.stat-label-good { color: #39d98a; }
.stat-label-warn { color: #ffb020; }
.stat-label-bad { color: #ff5d6c; }
</style>

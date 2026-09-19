<template>
  <div>
    <div class="kpi-row">
      <div class="card kpi" v-for="k in kpis" :key="k.label">
        <div class="kpi-value">{{ k.value }}</div>
        <div class="kpi-label">{{ k.label }}</div>
      </div>
    </div>
    <div class="grid-2">
      <div class="card">
        <h3>各批次平均良率</h3>
        <div ref="yieldChart" class="chart"></div>
      </div>
      <div class="card">
        <h3>缺陷类型帕累托</h3>
        <div ref="paretoChart" class="chart"></div>
      </div>
    </div>
    <div class="card" style="margin-top:20px">
      <h3>批次列表</h3>
      <table class="tbl">
        <thead>
          <tr><th>批次</th><th>产品</th><th>晶圆数</th><th>缺陷总数</th><th>平均良率</th></tr>
        </thead>
        <tbody>
          <tr v-for="l in lots" :key="l.id">
            <td>{{ l.name }}</td><td>{{ l.product || '—' }}</td>
            <td>{{ l.wafer_count }}</td><td>{{ l.defect_count }}</td>
            <td>
              <span class="yield-pill" :class="yieldClass(l.avg_yield)">{{ pct(l.avg_yield) }}</span>
            </td>
          </tr>
          <tr v-if="!lots.length"><td colspan="5" class="empty">暂无数据，请先到「数据导入」页导入或生成演示数据</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, shallowRef } from 'vue'
import * as echarts from 'echarts'
import { api, pct } from '../api'

const lots = ref([])
const kpis = ref([
  { label: '批次总数', value: '—' }, { label: '晶圆总数', value: '—' },
  { label: '缺陷总数', value: '—' }, { label: '平均良率', value: '—' },
])
const yieldChart = ref(null)
const paretoChart = ref(null)
const charts = shallowRef([])

function yieldClass(y) {
  if (y == null) return ''
  return y >= 0.95 ? 'good' : y >= 0.9 ? 'warn' : 'bad'
}

function renderYield(lotsData) {
  const chart = echarts.init(yieldChart.value)
  chart.setOption({
    tooltip: { trigger: 'axis', valueFormatter: v => (v * 100).toFixed(1) + '%' },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: lotsData.map(l => l.name) },
    yAxis: { type: 'value', min: v => Math.max(0, Math.floor(v.min * 10) / 10 - 0.05), max: 1,
             axisLabel: { formatter: v => (v * 100).toFixed(0) + '%' } },
    series: [{
      type: 'bar', data: lotsData.map(l => l.avg_yield), barMaxWidth: 48,
      itemStyle: { color: p => p.value >= 0.95 ? '#66bb6a' : p.value >= 0.9 ? '#ffa726' : '#ef5350',
                   borderRadius: [4, 4, 0, 0] },
      markLine: { silent: true, symbol: 'none',
                  lineStyle: { color: '#78909c', type: 'dashed' },
                  data: [{ yAxis: 0.95, label: { formatter: '目标 95%' } }] },
    }],
  })
  charts.value.push(chart)
}

function renderPareto(items) {
  const chart = echarts.init(paretoChart.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 50, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: items.map(i => `${i.name}`) },
    yAxis: [{ type: 'value', name: '数量' },
            { type: 'value', name: '累计%', max: 1,
              axisLabel: { formatter: v => (v * 100).toFixed(0) + '%' } }],
    series: [
      { name: '缺陷数', type: 'bar', barMaxWidth: 40,
        data: items.map(i => ({ value: i.count, itemStyle: { color: i.color, borderRadius: [4, 4, 0, 0] } })) },
      { name: '累计占比', type: 'line', yAxisIndex: 1, smooth: true,
        data: items.map(i => i.cumulative), itemStyle: { color: '#546e7a' } },
    ],
  })
  charts.value.push(chart)
}

onMounted(async () => {
  const [summary, lotsData, pareto] = await Promise.all([
    api.summary(), api.lots(), api.pareto(),
  ])
  lots.value = lotsData
  kpis.value = [
    { label: '批次总数', value: summary.lot_count },
    { label: '晶圆总数', value: summary.wafer_count },
    { label: '缺陷总数', value: summary.defect_count },
    { label: '平均良率', value: pct(summary.avg_yield) },
  ]
  renderYield(lotsData.filter(l => l.avg_yield != null))
  renderPareto(pareto.items)
  window.addEventListener('resize', () => charts.value.forEach(c => c.resize()))
})
</script>

<style scoped>
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
.kpi { text-align: center; padding: 18px; }
.kpi-value { font-size: 28px; font-weight: 700; color: #1976d2; }
.kpi-label { font-size: 13px; color: #78909c; margin-top: 4px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.chart { height: 300px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
.tbl th, .tbl td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #eceff1; }
.tbl th { color: #78909c; font-weight: 500; font-size: 13px; }
.empty { text-align: center; color: #90a4ae; padding: 24px; }
.yield-pill { padding: 3px 10px; border-radius: 12px; font-size: 13px; }
.yield-pill.good { background: #e8f5e9; color: #2e7d32; }
.yield-pill.warn { background: #fff3e0; color: #ef6c00; }
.yield-pill.bad { background: #ffebee; color: #c62828; }
</style>

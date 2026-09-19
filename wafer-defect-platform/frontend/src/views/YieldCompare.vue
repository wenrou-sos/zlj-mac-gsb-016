<template>
  <div>
    <div class="card controls">
      <span class="lbl">选择对比批次：</span>
      <label v-for="l in lots" :key="l.id" class="chk">
        <input type="checkbox" :value="l.id" v-model="selected" @change="refresh" />
        {{ l.name }}
      </label>
    </div>

    <div class="grid-2">
      <div class="card">
        <h3>批次平均良率对比</h3>
        <div ref="avgChart" class="chart"></div>
      </div>
      <div class="card">
        <h3>各晶圆良率分布</h3>
        <div ref="waferChart" class="chart"></div>
      </div>
    </div>

    <div class="card" style="margin-top:20px">
      <h3>明细数据</h3>
      <table class="tbl">
        <thead>
          <tr><th>批次</th><th>晶圆</th><th>总管芯</th><th>失效管芯</th><th>缺陷数</th><th>良率</th></tr>
        </thead>
        <tbody>
          <template v-for="lot in data" :key="lot.lot_id">
            <tr v-for="w in lot.wafers" :key="w.wafer_id">
              <td>{{ lot.name }}</td><td>#{{ w.wafer_number }}</td>
              <td>{{ w.total_dies }}</td><td>{{ w.defective_dies }}</td>
              <td>{{ w.defect_count }}</td>
              <td><span class="yield-pill" :class="yieldClass(w.yield)">{{ pct(w.yield) }}</span></td>
            </tr>
            <tr class="avg-row" v-if="lot.wafers.length">
              <td colspan="5">{{ lot.name }} 平均（{{ lot.wafer_count }} 片）</td>
              <td><strong>{{ pct(lot.avg_yield) }}</strong></td>
            </tr>
          </template>
          <tr v-if="!data.length"><td colspan="6" class="empty">请勾选至少一个批次</td></tr>
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
const selected = ref([])
const data = ref([])
const avgChart = ref(null)
const waferChart = ref(null)
const charts = shallowRef([])

function yieldClass(y) {
  return y >= 0.95 ? 'good' : y >= 0.9 ? 'warn' : 'bad'
}

function render() {
  charts.value.forEach(c => c.dispose())
  charts.value = []

  const a = echarts.init(avgChart.value)
  a.setOption({
    tooltip: { trigger: 'axis', valueFormatter: v => (v * 100).toFixed(1) + '%' },
    grid: { left: 55, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: data.value.map(l => l.name) },
    yAxis: { type: 'value', max: 1, axisLabel: { formatter: v => (v * 100).toFixed(0) + '%' } },
    series: [{
      type: 'bar', barMaxWidth: 56, data: data.value.map(l => l.avg_yield),
      itemStyle: { color: p => p.value >= 0.95 ? '#66bb6a' : p.value >= 0.9 ? '#ffa726' : '#ef5350',
                   borderRadius: [4, 4, 0, 0] },
      label: { show: true, position: 'top', formatter: p => (p.value * 100).toFixed(1) + '%' },
      markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: '#78909c' },
                  data: [{ yAxis: 0.95, label: { formatter: '目标 95%' } }] },
    }],
  })

  const w = echarts.init(waferChart.value)
  w.setOption({
    tooltip: { trigger: 'axis', valueFormatter: v => (v * 100).toFixed(1) + '%' },
    legend: { bottom: 0 },
    grid: { left: 55, right: 20, top: 30, bottom: 55 },
    xAxis: { type: 'category', name: '晶圆编号',
             data: [...new Set(data.value.flatMap(l => l.wafers.map(x => x.wafer_number)))].sort((a, b) => a - b) },
    yAxis: { type: 'value', max: 1, axisLabel: { formatter: v => (v * 100).toFixed(0) + '%' } },
    series: data.value.map((lot, i) => ({
      name: lot.name, type: 'line', smooth: true, symbolSize: 7,
      data: lot.wafers.map(x => [x.wafer_number, x.yield]),
      lineStyle: { width: 2 },
      emphasis: { focus: 'series' },
    })),
  })
  charts.value.push(a, w)
}

async function refresh() {
  if (!selected.value.length) { data.value = []; render(); return }
  data.value = (await api.yieldCompare(selected.value)).lots
  render()
}

onMounted(async () => {
  lots.value = await api.lots()
  selected.value = lots.value.map(l => l.id)  // 默认全选
  await refresh()
  window.addEventListener('resize', () => charts.value.forEach(c => c.resize()))
})
</script>

<style scoped>
.controls { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; margin-bottom: 20px; }
.lbl { font-size: 14px; color: #546e7a; }
.chk { display: flex; align-items: center; gap: 6px; font-size: 14px; cursor: pointer; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.chart { height: 320px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
.tbl th, .tbl td { padding: 9px 12px; text-align: left; border-bottom: 1px solid #eceff1; }
.tbl th { color: #78909c; font-weight: 500; font-size: 13px; }
.avg-row { background: #fafafa; }
.empty { text-align: center; color: #90a4ae; padding: 20px; }
.yield-pill { padding: 3px 10px; border-radius: 12px; font-size: 13px; }
.yield-pill.good { background: #e8f5e9; color: #2e7d32; }
.yield-pill.warn { background: #fff3e0; color: #ef6c00; }
.yield-pill.bad { background: #ffebee; color: #c62828; }
</style>

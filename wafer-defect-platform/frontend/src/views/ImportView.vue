<template>
  <div class="grid-2">
    <div class="card">
      <h3>导入检测数据</h3>
      <div class="row">
        <label class="field">网格行数
          <input type="number" v-model.number="dieRows" min="1" max="200" />
        </label>
        <label class="field">网格列数
          <input type="number" v-model.number="dieCols" min="1" max="200" />
        </label>
      </div>

      <div class="tabs">
        <button :class="{ on: tab === 'csv' }" @click="tab = 'csv'">CSV 文件</button>
        <button :class="{ on: tab === 'json' }" @click="tab = 'json'">JSON 粘贴</button>
      </div>

      <div v-if="tab === 'csv'" class="pane">
        <input type="file" accept=".csv" @change="onFile" />
        <p class="fmt">CSV 格式（含表头）：<code>lot,wafer,die_x,die_y,defect_code</code></p>
        <button class="btn ghost" @click="downloadSample">下载示例 CSV</button>
      </div>
      <div v-else class="pane">
        <textarea v-model="jsonText" rows="8"
          placeholder='[{"lot":"LOT-1","wafer":1,"die_x":5,"die_y":7,"defect_code":"SCR"}]'></textarea>
      </div>

      <div class="actions">
        <button class="btn" @click="submit" :disabled="loading">
          {{ loading ? '导入中…' : '开始导入' }}
        </button>
        <button class="btn ghost" @click="loadDemo" :disabled="loading">生成演示数据</button>
      </div>

      <div v-if="error" class="msg err">{{ error }}</div>
      <div v-if="result" class="msg ok">
        导入完成：{{ result.defects_imported }} 条缺陷，
        新建批次 {{ result.lots_created }} 个、晶圆 {{ result.wafers_created }} 片
        <template v-if="result.rows_skipped">，跳过 {{ result.rows_skipped }} 行</template>
        <ul v-if="result.errors.length" class="err-list">
          <li v-for="(e, i) in result.errors.slice(0, 5)" :key="i">{{ e }}</li>
        </ul>
      </div>
      <div v-if="demoMsg" class="msg ok">{{ demoMsg }}</div>
    </div>

    <div class="card">
      <h3>格式说明</h3>
      <table class="spec">
        <thead><tr><th>字段</th><th>说明</th><th>必填</th></tr></thead>
        <tbody>
          <tr><td><code>lot</code></td><td>批次号，不存在时自动创建</td><td>是</td></tr>
          <tr><td><code>wafer</code></td><td>晶圆编号（≥1）</td><td>是</td></tr>
          <tr><td><code>die_x</code></td><td>管芯列坐标 0 ~ 列数-1</td><td>是</td></tr>
          <tr><td><code>die_y</code></td><td>管芯行坐标 0 ~ 行数-1</td><td>是</td></tr>
          <tr><td><code>defect_code</code></td><td>缺陷类型代码，缺省 UNK</td><td>否</td></tr>
        </tbody>
      </table>
      <h3 style="margin-top:20px">内置缺陷类型</h3>
      <div class="types">
        <span v-for="t in defectTypes" :key="t.code" class="type-tag">
          <i :style="{ background: t.color }"></i>{{ t.code }} {{ t.name }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const tab = ref('csv')
const dieRows = ref(20)
const dieCols = ref(20)
const file = ref(null)
const jsonText = ref('')
const result = ref(null)
const error = ref('')
const demoMsg = ref('')
const loading = ref(false)
const defectTypes = ref([])

const SAMPLE = `lot,wafer,die_x,die_y,defect_code
LOT-001,1,5,7,SCR
LOT-001,1,5,8,SCR
LOT-001,1,6,7,PRT
LOT-001,1,12,3,CNT
LOT-001,2,9,9,PAT
LOT-001,2,10,10,PAT`

function onFile(e) { file.value = e.target.files[0] || null }

function downloadSample() {
  const url = URL.createObjectURL(new Blob([SAMPLE], { type: 'text/csv' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: 'sample_defects.csv' })
  a.click()
  URL.revokeObjectURL(url)
}

async function submit() {
  error.value = ''; result.value = null; demoMsg.value = ''
  loading.value = true
  try {
    if (tab.value === 'csv') {
      if (!file.value) throw new Error('请先选择 CSV 文件')
      result.value = await api.importCsv(file.value, dieRows.value, dieCols.value)
    } else {
      const records = JSON.parse(jsonText.value)
      if (!Array.isArray(records)) throw new Error('JSON 必须是记录数组')
      result.value = await api.importJson(records, dieRows.value, dieCols.value)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function loadDemo() {
  error.value = ''; demoMsg.value = ''; loading.value = true
  try {
    const r = await api.seedDemo()
    demoMsg.value = r.created
      ? `已生成演示批次：${r.lots.join('、')}，可到「晶圆图谱」查看`
      : '演示数据已存在（幂等跳过）'
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(async () => { defectTypes.value = await api.defectTypes() })
</script>

<style scoped>
.grid-2 { display: grid; grid-template-columns: 1.2fr 1fr; gap: 20px; }
.row { display: flex; gap: 16px; margin-bottom: 14px; }
.row .field { flex: 1; }
.tabs { display: flex; gap: 8px; margin-bottom: 12px; }
.tabs button {
  border: 1px solid #cfd8dc; background: #fff; border-radius: 6px;
  padding: 6px 16px; cursor: pointer; font-size: 13px; color: #607d8b;
}
.tabs button.on { background: #1976d2; border-color: #1976d2; color: #fff; }
.pane { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.pane textarea { width: 100%; font-family: monospace; font-size: 12px; }
.fmt { font-size: 12px; color: #90a4ae; }
.fmt code, .spec code { background: #eceff1; padding: 1px 6px; border-radius: 4px; }
.actions { display: flex; gap: 10px; margin-top: 16px; }
.err-list { margin-top: 6px; padding-left: 18px; color: #c62828; }
.spec { width: 100%; border-collapse: collapse; font-size: 13px; }
.spec th, .spec td { padding: 8px 10px; border-bottom: 1px solid #eceff1; text-align: left; }
.spec th { color: #78909c; font-weight: 500; }
.types { display: flex; flex-wrap: wrap; gap: 8px; }
.type-tag {
  display: inline-flex; align-items: center; gap: 6px; font-size: 12px;
  background: #eceff1; border-radius: 12px; padding: 4px 10px;
}
.type-tag i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
</style>

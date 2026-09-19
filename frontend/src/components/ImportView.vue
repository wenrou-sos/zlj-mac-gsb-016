<template>
  <div class="panel">
    <h2>导入检测点位与缺陷类型数据</h2>

    <div class="layout" style="grid-template-columns: 1fr 1fr;">
      <div>
        <div class="upload-zone" :class="{ drag: dragging }"
             @click="$refs.fileInput.click()"
             @dragover.prevent="dragging = true"
             @dragleave.prevent="dragging = false"
             @drop.prevent="onDrop">
          <div style="font-size: 28px;">📄</div>
          <div style="margin-top: 8px;">点击选择或拖拽 <b>CSV / JSON</b> 文件到此处</div>
          <div class="muted" style="margin-top: 6px;">
            CSV 支持列名：batch/lot、wafer、x/x_mm、y/y_mm、defect_type（支持中英文表头）
          </div>
        </div>
        <input ref="fileInput" type="file" accept=".csv,.json"
               style="display:none" @change="onPick" />

        <div style="display:flex; gap:10px; margin-top:14px;">
          <div class="field" style="flex:1">
            <label>批次名称（可选，覆盖文件中的批次列）</label>
            <input type="text" v-model="batchName" placeholder="例如 LOT-2026-0919" />
          </div>
          <div class="field" style="flex:1">
            <label>产品型号（可选）</label>
            <input type="text" v-model="product" placeholder="例如 MCU-7nm" />
          </div>
        </div>

        <div style="display:flex; gap:10px; margin-top:4px;">
          <button class="btn" :disabled="!file || uploading" @click="upload">
            <span v-if="uploading" class="spinner"></span> 导入数据
          </button>
          <button class="btn ghost" @click="seedDemo" :disabled="seeding">
            {{ seeding ? '生成中…' : '载入内置演示数据（3 个批次）' }}
          </button>
          <a class="btn ghost" href="/sample_wafer_data.csv" download
             style="text-decoration:none; display:inline-flex; align-items:center;">
            下载 CSV 示例
          </a>
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <div v-if="result" style="margin-top:14px; padding:12px; background:var(--panel-2); border-radius:8px; font-size:13px;">
          ✅ 已导入批次 <b>{{ result.batch_name }}</b>：{{ result.wafer_count }} 片晶圆，
          {{ result.point_count }} 个检测点位，其中缺陷 {{ result.defect_count }} 个。
          <div style="margin-top:6px;">
            <button class="btn ghost" style="padding:4px 10px; font-size:12px;"
                    @click="$emit('imported', result.batch_id)">
              前往查看图谱 →
            </button>
          </div>
        </div>
      </div>

      <div>
        <h2 style="font-size:13px; color:var(--text-dim);">CSV 格式示例</h2>
        <pre style="background:var(--panel-2); padding:14px; border-radius:8px; font-size:12px;
                    color:#bcd; overflow:auto; margin:0;">batch,wafer,x,y,defect_type
LOT-001,W01,-150,-150,GOOD
LOT-001,W01,-140,-150,GOOD
LOT-001,W01,-130,-140,PARTICLE
LOT-001,W01,-120,-130,SCRATCH
LOT-001,W02,...,GOOD</pre>
        <h2 style="font-size:13px; color:var(--text-dim); margin-top:16px;">缺陷类型代码</h2>
        <div class="muted" style="line-height:1.9;">
          <code>GOOD / OK / 正常</code> 计为合格点；其余值（PARTICLE、SCRATCH、CRACK、
          STAIN、MISSING_DIE、ETCH_DEFECT 或自定义代码）均计为缺陷点并参与聚类分析。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api.js'

const emit = defineEmits(['imported'])

const file = ref(null)
const batchName = ref('')
const product = ref('')
const uploading = ref(false)
const seeding = ref(false)
const dragging = ref(false)
const error = ref('')
const result = ref(null)

function onPick(e) {
  file.value = e.target.files[0] || null
  error.value = ''
}
function onDrop(e) {
  dragging.value = false
  file.value = e.dataTransfer.files[0] || null
  error.value = ''
}

async function upload() {
  if (!file.value) return
  uploading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await api.uploadFile(file.value, batchName.value.trim(), product.value.trim())
  } catch (e) {
    error.value = `导入失败：${e.message}`
  } finally {
    uploading.value = false
  }
}

async function seedDemo() {
  seeding.value = true
  error.value = ''
  try {
    const r = await api.seedDemo()
    if (r.status === 'seeded') {
      result.value = {
        batch_name: r.batches.map(b => b.batch).join('、'),
        wafer_count: 6,
        point_count: r.batches.reduce((s, b) => s + b.points, 0),
        defect_count: 0,
        batch_id: null
      }
    } else {
      error.value = '演示数据已存在，未重复生成（可在批次页删除后重试）'
    }
    emit('imported')
  } catch (e) {
    error.value = `生成失败：${e.message}`
  } finally {
    seeding.value = false
  }
}
</script>

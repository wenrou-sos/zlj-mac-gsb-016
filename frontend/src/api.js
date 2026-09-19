const BASE = ''

async function request(path, options = {}) {
  const resp = await fetch(BASE + path, {
    headers: { 'Accept': 'application/json' },
    ...options
  })
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`
    try {
      const body = await resp.json()
      detail = body.detail || detail
    } catch (_) { /* ignore */ }
    throw new Error(detail)
  }
  return resp.json()
}

export const api = {
  health: () => request('/health'),
  listBatches: () => request('/api/batches'),
  deleteBatch: (id) => request(`/api/batches/${id}`, { method: 'DELETE' }),
  listWafers: (batchId) =>
    request(batchId != null ? `/api/wafers?batch_id=${batchId}` : '/api/wafers'),
  waferMap: (waferId) => request(`/api/wafers/${waferId}/map`),
  compare: (ids = null) =>
    request(ids && ids.length ? `/api/batches/compare?batch_ids=${ids.join(',')}` : '/api/batches/compare'),
  seedDemo: () => request('/api/admin/seed', { method: 'POST' }),
  uploadFile: (file, batchName, product) => {
    const form = new FormData()
    form.append('file', file)
    const params = new URLSearchParams()
    if (batchName) params.set('batch_name', batchName)
    if (product) params.set('product', product)
    const qs = params.toString()
    return request(`/api/import/file${qs ? `?${qs}` : ''}`, { method: 'POST', body: form })
  }
}

export const DEFECT_TYPE_LABELS = {
  GOOD: '正常',
  PARTICLE: '颗粒',
  SCRATCH: '划伤',
  CRACK: '裂纹',
  STAIN: '沾污',
  MISSING_DIE: '缺片',
  ETCH_DEFECT: '刻蚀缺陷'
}

export const PATTERN_LABELS = {
  random: '随机分布（正常）',
  cluster: '局部聚集',
  ring: '边缘环',
  center: '中心聚集',
  scratch: '划伤'
}

// 缺陷类型 -> 稳定颜色（哈希调色板）
const PALETTE = ['#ff6b81', '#ffd166', '#8be9fd', '#bd93f9', '#ff9f43',
  '#7bed9f', '#ff7675', '#74b9ff', '#a29bfe', '#55efc4', '#fd79a8']
export function defectColor(type) {
  if (!type || type === 'GOOD') return '#22324c'
  let h = 0
  for (let i = 0; i < type.length; i++) h = (h * 31 + type.charCodeAt(i)) >>> 0
  return PALETTE[h % PALETTE.length]
}

export function pct(x, digits = 2) {
  return `${(x * 100).toFixed(digits)}%`
}

export function yieldClass(y) {
  if (y >= 0.97) return 'good'
  if (y >= 0.93) return 'warn'
  return 'bad'
}

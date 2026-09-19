/** 后端 API 封装：统一错误处理与基地址。 */
const BASE = '/api'

async function req(path, options = {}) {
  const resp = await fetch(BASE + path, options)
  if (!resp.ok) {
    let detail = resp.statusText
    try { detail = (await resp.json()).detail || detail } catch { /* 非 JSON 响应 */ }
    throw new Error(detail)
  }
  return resp.status === 204 ? null : resp.json()
}

export const api = {
  health: () => req('/health'),
  summary: () => req('/analytics/summary'),
  lots: () => req('/lots'),
  wafers: (lotId) => req('/wafers' + (lotId ? `?lot_id=${lotId}` : '')),
  waferMap: (id) => req(`/wafers/${id}/map`),
  clusters: (id, eps, minSamples) =>
    req(`/wafers/${id}/clusters?eps=${eps}&min_samples=${minSamples}`),
  defectTypes: () => req('/defect-types'),
  yieldCompare: (ids) =>
    req('/analytics/yield' + (ids && ids.length ? `?lot_ids=${ids.join(',')}` : '')),
  pareto: (lotId) => req('/analytics/pareto' + (lotId ? `?lot_id=${lotId}` : '')),
  importCsv: (file, dieRows, dieCols) => {
    const fd = new FormData()
    fd.append('file', file)
    return req(`/import/csv?die_rows=${dieRows}&die_cols=${dieCols}`,
               { method: 'POST', body: fd })
  },
  importJson: (records, dieRows, dieCols) =>
    req(`/import/json?die_rows=${dieRows}&die_cols=${dieCols}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(records)
    }),
  seedDemo: () => req('/demo/seed', { method: 'POST' }),
  deleteLot: (id) => req(`/lots/${id}`, { method: 'DELETE' }),
}

export function pct(v) {
  return v == null ? '—' : (v * 100).toFixed(1) + '%'
}

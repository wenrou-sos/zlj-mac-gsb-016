<template>
  <div class="layout">
    <header class="topbar">
      <div class="brand">
        <span class="logo">◉</span>
        <span>晶圆缺陷图谱分析平台</span>
      </div>
      <nav>
        <router-link v-for="r in routes" :key="r.path" :to="r.path"
                     :class="{ active: $route.path === r.path }">
          {{ r.meta.title }}
        </router-link>
      </nav>
      <div class="health" :class="healthOk ? 'ok' : 'bad'">
        {{ healthOk ? '● 服务正常' : '● 服务异常' }}
      </div>
    </header>
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from './api'

const routes = [
  { path: '/', meta: { title: '仪表盘' } },
  { path: '/map', meta: { title: '晶圆图谱' } },
  { path: '/yield', meta: { title: '良率对比' } },
  { path: '/import', meta: { title: '数据导入' } },
]
const healthOk = ref(false)

onMounted(async () => {
  try { await api.health(); healthOk.value = true } catch { healthOk.value = false }
})
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
  background: #f0f2f5; color: #2c3e50;
}
.layout { min-height: 100vh; display: flex; flex-direction: column; }
.topbar {
  display: flex; align-items: center; gap: 32px;
  background: #1f2d3d; color: #fff; padding: 0 24px; height: 56px;
}
.brand { font-size: 17px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.logo { color: #4fc3f7; font-size: 20px; }
nav { display: flex; gap: 4px; flex: 1; }
nav a {
  color: #b0bec5; text-decoration: none; padding: 6px 14px;
  border-radius: 6px; font-size: 14px; transition: all .2s;
}
nav a:hover { color: #fff; }
nav a.active { color: #fff; background: rgba(79, 195, 247, .25); }
.health { font-size: 12px; }
.health.ok { color: #69f0ae; }
.health.bad { color: #ff8a80; }
main { flex: 1; padding: 24px; max-width: 1400px; width: 100%; margin: 0 auto; }

.card {
  background: #fff; border-radius: 10px; padding: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, .08);
}
.card h3 { font-size: 15px; margin-bottom: 14px; color: #37474f; }
.btn {
  background: #1976d2; color: #fff; border: none; border-radius: 6px;
  padding: 8px 18px; font-size: 14px; cursor: pointer; transition: background .2s;
}
.btn:hover { background: #1565c0; }
.btn:disabled { background: #90a4ae; cursor: not-allowed; }
.btn.ghost { background: #eceff1; color: #37474f; }
.btn.ghost:hover { background: #cfd8dc; }
select, input[type=number], textarea {
  border: 1px solid #cfd8dc; border-radius: 6px; padding: 7px 10px;
  font-size: 14px; font-family: inherit; background: #fff;
}
label.field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #607d8b; }
.msg { padding: 10px 14px; border-radius: 6px; font-size: 13px; margin-top: 12px; }
.msg.ok { background: #e8f5e9; color: #2e7d32; }
.msg.err { background: #ffebee; color: #c62828; }
</style>

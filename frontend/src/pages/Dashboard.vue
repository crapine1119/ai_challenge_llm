<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-semibold">JD 현황 통계</h1>
    <KPIGrid :items="kpis" />
    <SimpleLineChart :labels="labels" :data="data" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import KPIGrid from '@/components/dashboard/KPIGrid.vue'
import SimpleLineChart from '@/components/dashboard/SimpleLineChart.vue'
const kpis = ref([
  { label: '총 생성 수', value: 0 },
  { label: '평균 초안 시간', value: '—' },
  { label: '실패율', value: '—' }
])
const labels = ref<string[]>([])   // PLACEHOLDER
const data = ref<number[]>([])     // PLACEHOLDER
</script>

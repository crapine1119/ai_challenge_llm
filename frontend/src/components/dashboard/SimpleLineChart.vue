<template>
  <canvas ref="canvas" />
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Chart, LineController, LineElement, PointElement, LinearScale, Title, CategoryScale } from 'chart.js'
Chart.register(LineController, LineElement, PointElement, LinearScale, Title, CategoryScale)

const props = defineProps<{ labels: string[]; data: number[] }>()
const canvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

onMounted(() => {
  if (!canvas.value) return
  chart = new Chart(canvas.value, {
    type: 'line',
    data: {
      labels: props.labels,
      datasets: [{ data: props.data }]
    },
    options: { responsive: true, maintainAspectRatio: false }
  })
})

watch(() => [props.labels, props.data], () => {
  if (chart) {
    chart.data.labels = props.labels
    chart.data.datasets[0].data = props.data
    chart.update()
  }
})
</script>

<style scoped>
:host, canvas { display:block; width:100%; height:260px; }
</style>

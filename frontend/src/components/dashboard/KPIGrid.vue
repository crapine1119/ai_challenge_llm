<template>
  <div class="grid gap-3 md:grid-cols-3">
    <div v-for="k in items" :key="k.label" class="rounded-lg border bg-white p-4 shadow-sm">
      <div class="text-xs text-gray-500">{{ k.label }}</div>
      <div class="mt-1 text-xl font-semibold">{{ k.value }}</div>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ items: { label: string; value: any }[] }>()
</script>

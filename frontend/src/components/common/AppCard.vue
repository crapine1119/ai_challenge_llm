<template>
  <div class="rounded-lg border bg-white p-4 shadow-sm">
    <div class="mb-2 flex items-center justify-between">
      <h3 class="font-medium">{{ title }}</h3>
      <span v-if="badge" class="rounded bg-gray-100 px-2 py-0.5 text-xs">{{ badge }}</span>
    </div>
    <div><slot /></div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ title: string; badge?: string }>()
</script>

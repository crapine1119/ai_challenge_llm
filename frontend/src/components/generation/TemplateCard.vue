<template>
  <div class="cursor-pointer rounded-lg border bg-white p-4 shadow-sm hover:border-gray-400" @click="$emit('select')">
    <div class="mb-1 font-medium">{{ label }}</div>
    <div class="text-sm text-gray-600">{{ subtitle }}</div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ label: string; subtitle?: string }>()
defineEmits<{ (e: 'select'): void }>()
</script>

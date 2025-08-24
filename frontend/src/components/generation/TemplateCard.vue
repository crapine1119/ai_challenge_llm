<!-- src/components/generation/TemplateCard.vue -->
<template>
  <div
    class="cursor-pointer rounded-lg border bg-white p-4 shadow-sm hover:border-gray-400"
    :class="active ? 'ring-2 ring-gray-800 border-gray-800' : ''"
    @click="$emit('select')"
  >
    <div class="mb-1 font-medium">{{ label }}</div>
    <div class="text-sm text-gray-600">{{ subtitle }}</div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ label: string; subtitle?: string; active?: boolean }>()
defineEmits<{ (e: 'select'): void }>()
</script>

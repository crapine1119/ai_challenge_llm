<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 z-[1000] flex items-center justify-center">
      <div class="absolute inset-0 bg-black/40" @click="onBackdrop" />
      <div class="relative z-[1001] w-[min(720px,92vw)] max-h-[88vh] overflow-auto rounded-xl bg-white p-5 shadow-xl">
        <header class="mb-3 flex items-center justify-between">
          <h3 class="text-lg font-semibold">{{ title }}</h3>
          <button class="rounded px-2 py-1 text-sm hover:bg-gray-100" @click="$emit('update:modelValue', false)">✕</button>
        </header>
        <div><slot /></div>
        <footer v-if="$slots.footer" class="mt-4 flex items-center justify-end gap-2">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
const props = defineProps<{ modelValue: boolean; title?: string; closeOnBackdrop?: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

function onBackdrop() {
  if (props.closeOnBackdrop !== false) emit('update:modelValue', false)
}
</script>

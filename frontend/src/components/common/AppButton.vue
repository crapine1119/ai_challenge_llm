<template>
  <button
    :class="[
      'inline-flex items-center justify-center rounded-md px-3 py-2 text-sm transition',
      variant === 'primary' && 'bg-black text-white hover:bg-gray-800',
      variant === 'secondary' && 'bg-gray-800 text-white hover:bg-gray-700',
      variant === 'ghost' && 'hover:bg-gray-100',
      size === 'sm' && 'px-2 py-1 text-xs'
    ]"
    v-bind="$attrs"
  >
    <slot />
  </button>
</template>
<script setup lang="ts">
withDefaults(defineProps<{ variant?: 'primary'|'secondary'|'ghost'; size?: 'sm'|'md' }>(), {
  variant: 'primary',
  size: 'md'
})
</script>

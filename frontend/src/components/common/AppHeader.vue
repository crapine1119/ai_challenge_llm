<template>
  <header class="border-b bg-white">
    <div class="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
      <router-link to="/" class="font-semibold">Job Korea JD Generator</router-link>

      <nav class="flex items-center gap-4 text-sm">
        <router-link to="/analyze">JD 분석</router-link>
        <router-link to="/generate/realtime">실시간 생성</router-link>
        <router-link to="/collect">직무 추가</router-link>
        <router-link to="/generate/board">갤러리 (TODO)</router-link>
        <button class="ml-2 rounded-md border px-3 py-1.5 hover:bg-gray-50" @click="openChangeModal">
          직무 변경
        </button>
      </nav>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useUIStore } from '@/store/ui'
import { useCatalogStore } from '@/store/catalog'

const ui = useUIStore()
const catalog = useCatalogStore()

function openChangeModal() {
  ui.openJobModalForChange({
    company_code: catalog.selectedCompany?.company_code || '',
    job_code: catalog.selectedJob?.job_code || ''
  })
}
</script>

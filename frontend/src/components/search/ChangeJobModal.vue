<!-- src/components/search/ChangeJobModal.vue -->
<template>
  <AppModal v-model="open" title="회사·직무 변경">
    <CompanyJobSelect />

    <template #footer>
      <button class="rounded-md px-3 py-2 text-sm hover:bg-gray-100" @click="cancel">취소</button>
      <button
        class="rounded-md bg-black px-3 py-2 text-sm text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="!ready"
        @click="save"
      >
        저장
      </button>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import AppModal from '@/components/common/AppModal.vue'
import CompanyJobSelect from '@/components/search/CompanyJobSelect.vue'
import { useUIStore } from '@/store/ui'
import { useCatalogStore } from '@/store/catalog'

const ui = useUIStore()
const catalog = useCatalogStore()

const open = computed({
  get: () => ui.showJobModal,
  set: (v: boolean) => (ui.showJobModal = v)
})

const ready = computed(() => !!(catalog.selectedCompany && catalog.selectedJob))

function cancel() { ui.closeJobModal() }
function save() {
  if (!ready.value) return
  // 선택은 chooseCompany/chooseJob에서 이미 localStorage에 저장됨
  ui.closeJobModal()
}

watch(open, async (v) => { if (v) await catalog.ensureLoaded() }, { immediate: true })
</script>

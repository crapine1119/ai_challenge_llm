<template>
  <AppModal v-model="open" :title="titleText">
    <div class="space-y-3">
      <CompanyJobSelect />

      <!-- 강제 변경 모드 안내 및 유효성 -->
      <div v-if="mustChange" class="rounded-md bg-amber-50 p-3 text-xs text-amber-800">
        직무를 <b>현재 선택과 다른 값</b>으로 변경해야 저장할 수 있어요.
      </div>
      <div v-if="mustChange && ready && !changed" class="text-xs text-red-600">
        현재 선택과 동일합니다. 다른 직무를 선택하세요.
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <button class="rounded border px-3 py-1.5 hover:bg-gray-50" @click="cancel">취소</button>
        <button
          class="rounded bg-black px-3 py-1.5 text-white disabled:opacity-50"
          :disabled="!allowSave"
          @click="save"
        >
          적용
        </button>
      </div>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { computed, watch, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppModal from '@/components/common/AppModal.vue'
import CompanyJobSelect from '@/components/search/CompanyJobSelect.vue'
import { useUIStore } from '@/store/ui'
import { useCatalogStore } from '@/store/catalog'

const ui = useUIStore()
const catalog = useCatalogStore()
const route = useRoute()
const router = useRouter()

const open = computed({
  get: () => ui.showJobModal,
  set: (v: boolean) => (ui.showJobModal = v)
})

const mustChange = computed(() => ui.forceChange)
const snapshot = ref({ company_code: '', job_code: '' })

const ready = computed(() => !!(catalog.selectedCompany && catalog.selectedJob))
const changed = computed(() => {
  // 회사 변경 여부는 선택사항이지만, "직무 변경"은 반드시 다르게
  const currentJob = catalog.selectedJob?.job_code || ''
  return currentJob && currentJob !== snapshot.value.job_code
})
const allowSave = computed(() => ready.value && (!mustChange.value || changed.value))

const titleText = computed(() =>
  mustChange.value ? '직무 변경' : '회사 · 직무 선택'
)

function cancel() {
  ui.closeJobModal()
}

async function save() {
  if (!allowSave.value) return
  ui.closeJobModal()
  // 쿼리 동기화
  const q: any = {
    ...route.query,
    company_code: catalog.selectedCompany?.company_code || '',
    job_code: catalog.selectedJob?.job_code || ''
  }
  await router.replace({ query: q })
}

watch(open, async (v) => {
  if (v) {
    // 모달 오픈 순간의 이전 선택 스냅샷 저장(강제 변경 비교 기준)
    snapshot.value = {
      company_code: ui.changeSnapshot.company_code || catalog.selectedCompany?.company_code || '',
      job_code: ui.changeSnapshot.job_code || catalog.selectedJob?.job_code || ''
    }
    // 회사/직무 데이터 로드 보장
    await catalog.ensureLoaded()
  }
})

onMounted(async () => {
  if (open.value) {
    await catalog.ensureLoaded()
  }
})
</script>

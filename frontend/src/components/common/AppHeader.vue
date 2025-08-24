                                                    <template>
  <header class="border-b bg-white">
    <div class="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
      <router-link to="/" class="font-semibold">JD Generator</router-link>

      <nav class="flex items-center gap-4 text-sm">
        <router-link to="/collect">직무 추가</router-link>
        <router-link to="/generate/board">게시판 (TODO)</router-link>
        <router-link to="/generate/stats">통계 (TODO)</router-link>

        <!-- 우측: 직무 변경 버튼 -->
        <button
          class="ml-2 rounded-md border px-3 py-1.5 hover:bg-gray-50"
          @click="openModal"
          title="회사·직무 변경"
        >
          직무 변경
        </button>
      </nav>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useUIStore } from '@/store/ui'
import { useCatalogStore } from '@/store/catalog'

const ui = useUIStore()
const catalog = useCatalogStore()

function openModal() { ui.openJobModal() }

/** 최초 진입 시 자동 팝업 */
onMounted(async () => {
  // 회사 목록/직무 목록 프리로드
  if (!catalog.companies.length) await catalog.loadCompanies()

  const flagKey = 'jobPickerAutoOpened'
  const already = sessionStorage.getItem(flagKey) === '1'
  const need = !(catalog.selectedCompany && catalog.selectedJob)

  if (need && !already) {
    ui.openJobModal()
    sessionStorage.setItem(flagKey, '1')
  }
})
</script>

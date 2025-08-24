<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-semibold">실시간 JD 생성</h1>

    <!-- 템플릿 선택 -->
    <div class="grid gap-4 md:grid-cols-4">
      <TemplateCard label="일반형" subtitle="균형 잡힌 기본형" @select="selectTemplate('neutral')" />
      <TemplateCard label="간결형" subtitle="짧고 핵심만" @select="selectTemplate('concise')" />
      <TemplateCard label="문화 스토리형" subtitle="회사 가치 강조" @select="selectTemplate('culture')" />
      <TemplateCard label="스킬 우선형" subtitle="요건·기술 중심" @select="selectTemplate('skills')" />
    </div>

    <div class="flex gap-3">
      <AppButton :disabled="!template" @click="start">이 템플릿으로 시작</AppButton>
      <AppButton variant="ghost" @click="openWait">대기 허브 보기</AppButton>
    </div>

    <!-- 진행 상태 & 미리보기 -->
    <ProgressBar v-if="status !== 'idle'" :status="status" />
    <section v-if="content" class="rounded-lg border bg-white p-4 shadow-sm">
      <h2 class="mb-2 font-medium">실시간 생성 미리보기</h2>
      <pre class="whitespace-pre-wrap">{{ content }}</pre>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGenerationStore } from '@/store/generation'
import AppButton from '@/components/common/AppButton.vue'
import TemplateCard from '@/components/generation/TemplateCard.vue'
import ProgressBar from '@/components/generation/ProgressBar.vue'

const router = useRouter()
const store = useGenerationStore()
const template = ref<string>('')

function selectTemplate(t: string) { template.value = t }

const status = computed(() => store.status)
const content = computed(() => store.content)

function start() {
  store.startGenerate({
    provider: 'openai',            // 백엔드 스펙에 맞게 조정
    model: 'gpt-4o-mini',
    template: template.value,
    // company / role / knowledge_override 등 필요 입력
  })
}

function openWait() {
  router.push({ name: 'wait-hub', query: { rid: store.requestId } })
}
</script>

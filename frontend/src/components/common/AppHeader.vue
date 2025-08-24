<template>
  <header class="border-b bg-white">
    <div class="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
      <router-link to="/" class="font-semibold">JD Generator</router-link>
      <nav class="flex gap-4 text-sm">
        <router-link to="/generate/realtime">실시간 생성</router-link>
        <router-link to="/generate/board">게시판</router-link>
        <router-link to="/generate/stats">통계</router-link>
        <router-link to="/collect">직무 추가</router-link>
      </nav>
    </div>
  </header>
</template>
<script setup lang="ts"></script>

<script setup lang="ts">
import { configState } from '@/store/config'
</script>

<template>
  <footer class="mt-auto py-8 border-t border-white/5 text-center">
    <p class="text-[10px] font-bold text-slate-700 uppercase tracking-widest">
      © 2026 Jean Schmitz • Released under MIT License • TaleWeaver v{{ configState.appVersion }}
    </p>
  </footer>
</template>

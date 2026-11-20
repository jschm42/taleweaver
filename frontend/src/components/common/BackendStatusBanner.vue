<script setup lang="ts">
/** Shows that the backend is unreachable (and when it is back), instead of a seemingly frozen UI. */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { WifiOff, RefreshCw, CheckCircle2 } from 'lucide-vue-next'
import { backendStatus, probeBackend } from '@/services/backendStatus'

const route = useRoute()
/** The login page shows its own "Engine starting up..." status, so the banner stays hidden there. */
const hiddenOnRoute = computed((): boolean => route.name === 'login')

const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | undefined

const secondsToRetry = computed((): number =>
  backendStatus.nextRetryAt ? Math.max(0, Math.ceil((backendStatus.nextRetryAt - now.value) / 1000)) : 0,
)
const offlineFor = computed((): string => {
  if (!backendStatus.offlineSince) return ''
  const seconds = Math.round((now.value - backendStatus.offlineSince) / 1000)
  return seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min`
})

onMounted(() => {
  ticker = setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (ticker) clearInterval(ticker)
})
</script>

<template>
  <Transition name="backend-banner">
    <div
      v-if="!hiddenOnRoute && !backendStatus.online"
      class="fixed top-3 left-1/2 -translate-x-1/2 z-[400] w-[min(92vw,34rem)] rounded-2xl border border-rose-500/40 bg-rose-950/90 px-4 py-3 text-rose-100 shadow-2xl backdrop-blur-xl"
      role="alert"
      aria-live="assertive"
    >
      <div class="flex items-start gap-3">
        <WifiOff class="mt-0.5 h-5 w-5 shrink-0 text-rose-300" />
        <div class="min-w-0 flex-1 text-xs leading-relaxed">
          <p class="font-black uppercase tracking-wider text-rose-200">Server not reachable</p>
          <p class="text-rose-100/80">
            The TaleWeaver backend does not answer (for {{ offlineFor }}). Actions may fail until it is back;
            the page reconnects on its own.
          </p>
          <p class="mt-1 text-[11px] text-rose-200/70">
            <template v-if="backendStatus.checking">Checking…</template>
            <template v-else-if="secondsToRetry">Next try in {{ secondsToRetry }} s.</template>
          </p>
          <p v-if="backendStatus.lastFailure" class="mt-0.5 text-[11px] text-rose-200/60">
            Last check: {{ backendStatus.lastFailure }}
          </p>
        </div>
        <button
          type="button"
          :disabled="backendStatus.checking"
          class="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-rose-300/30 bg-rose-500/20 px-2.5 py-1.5 text-[10px] font-black uppercase tracking-wider text-rose-50 hover:bg-rose-500/35 disabled:opacity-50"
          @click="probeBackend()"
        >
          <RefreshCw :class="['h-3 w-3', backendStatus.checking ? 'animate-spin' : '']" /> Retry now
        </button>
      </div>
    </div>
    <div
      v-else-if="!hiddenOnRoute && backendStatus.justRestored"
      class="fixed top-3 left-1/2 -translate-x-1/2 z-[400] inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-950/90 px-4 py-2 text-xs font-bold text-emerald-100 shadow-2xl backdrop-blur-xl"
      role="status"
      aria-live="polite"
    >
      <CheckCircle2 class="h-4 w-4 text-emerald-300" /> Connection restored
    </div>
  </Transition>
</template>

<style scoped>
.backend-banner-enter-active,
.backend-banner-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.backend-banner-enter-from,
.backend-banner-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}
</style>

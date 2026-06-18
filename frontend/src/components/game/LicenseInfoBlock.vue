<script setup lang="ts">
import { computed } from 'vue'
import { ScrollText, ExternalLink } from 'lucide-vue-next'
import type { ChatMessage } from '@/types'

const props = defineProps<{ msg: ChatMessage }>()

interface LicensePayload {
  creator?: string | null
  copyright?: string | null
  license?: string | null
  license_url?: string | null
}

const payload = computed<LicensePayload | null>(() => {
  try {
    const parsed = JSON.parse(props.msg.content)
    if (parsed && typeof parsed === 'object') return parsed as LicensePayload
  } catch {
    /* fall through */
  }
  return null
})

const hasAny = computed(() => {
  const p = payload.value
  if (!p) return false
  return !!(p.creator || p.copyright || p.license || p.license_url)
})
</script>

<template>
  <div
    v-if="hasAny"
    class="my-2.5 mx-1 relative overflow-hidden rounded-xl border border-amber-500/20 bg-gradient-to-r from-amber-500/[0.06] via-slate-950/40 to-slate-950/20 backdrop-blur-md shadow-lg shadow-black/10 px-4 py-2.5 text-xs text-slate-400 font-medium"
  >
    <div class="absolute inset-y-0 left-0 w-[3px] bg-amber-500/30"></div>

    <div class="relative flex flex-wrap items-center gap-x-4 gap-y-1.5 pl-1.5">
      <!-- Icon & Title Header -->
      <div class="flex items-center gap-2 shrink-0 text-amber-400 font-bold uppercase tracking-wider text-[10px]">
        <ScrollText class="w-3.5 h-3.5 text-amber-400" />
        <span>License & Credits:</span>
      </div>

      <!-- Single Line Metadata Info -->
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-slate-300">
        <!-- Creator -->
        <span v-if="payload?.creator" class="flex items-center gap-1">
          <span class="text-slate-500 font-semibold">Creator:</span>
          <span class="font-bold text-slate-200">{{ payload.creator }}</span>
        </span>

        <span v-if="payload?.creator && (payload?.copyright || payload?.license)" class="text-slate-700 select-none">•</span>

        <!-- Copyright -->
        <span v-if="payload?.copyright" class="flex items-center gap-1">
          <span class="text-slate-200 font-semibold">{{ payload.copyright }}</span>
        </span>

        <span v-if="payload?.copyright && payload?.license" class="text-slate-700 select-none">•</span>

        <!-- License -->
        <span v-if="payload?.license">
          <span class="text-slate-500 font-semibold mr-1">License:</span>
          <a
            v-if="payload?.license_url"
            :href="payload.license_url"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-0.5 font-bold text-amber-300 hover:text-amber-200 underline decoration-amber-500/40 hover:decoration-amber-400/60 transition-colors"
          >
            {{ payload.license }}
            <ExternalLink class="w-2.5 h-2.5 opacity-70 group-hover:opacity-100" />
          </a>
          <span v-else class="font-bold text-slate-200">{{ payload.license }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

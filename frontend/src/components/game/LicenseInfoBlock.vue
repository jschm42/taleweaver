<script setup lang="ts">
import { computed } from 'vue'
import { ScrollText, ExternalLink, User, Copyright, Link2 } from 'lucide-vue-next'
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
    class="my-4 mx-1 relative overflow-hidden rounded-2xl border border-amber-400/30 bg-gradient-to-br from-amber-500/[0.08] via-slate-900/40 to-slate-900/20 backdrop-blur-md shadow-xl shadow-black/30"
  >
    <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-400/60 to-transparent"></div>
    <div class="absolute -top-12 -right-12 w-40 h-40 bg-amber-400/10 rounded-full blur-3xl pointer-events-none"></div>

    <div class="relative p-5 space-y-3">
      <div class="flex items-center gap-2.5">
        <div class="p-2 rounded-xl bg-amber-500/15 border border-amber-400/30 shadow-inner">
          <ScrollText class="w-4 h-4 text-amber-300" />
        </div>
        <div>
          <p class="text-[10px] font-black text-amber-300 uppercase tracking-[0.3em]">License & Credits</p>
          <p class="text-[10px] text-slate-500 italic mt-0.5">Provenance of this adventure</p>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <div
          v-if="payload?.license"
          class="p-3 rounded-xl bg-black/30 border border-amber-400/15"
        >
          <div class="flex items-center gap-1.5 text-[9px] font-black text-amber-300/80 uppercase tracking-[0.25em] mb-1">
            <ScrollText class="w-3 h-3" />
            License
          </div>
          <div class="text-sm font-bold text-amber-100 leading-snug">{{ payload.license }}</div>
        </div>

        <a
          v-if="payload?.license_url"
          :href="payload.license_url"
          target="_blank"
          rel="noopener noreferrer"
          class="p-3 rounded-xl bg-black/30 border border-emerald-400/20 hover:border-emerald-400/50 hover:bg-emerald-500/[0.06] transition-all group/link block"
        >
          <div class="flex items-center gap-1.5 text-[9px] font-black text-emerald-400/80 uppercase tracking-[0.25em] mb-1">
            <Link2 class="w-3 h-3" />
            License URL
            <ExternalLink class="w-2.5 h-2.5 ml-auto opacity-50 group-hover/link:opacity-100 transition-opacity" />
          </div>
          <div class="text-xs font-mono text-emerald-300 group-hover/link:text-emerald-200 break-all leading-snug">{{ payload.license_url }}</div>
        </a>

        <div
          v-if="payload?.creator"
          class="p-3 rounded-xl bg-black/30 border border-white/5"
        >
          <div class="flex items-center gap-1.5 text-[9px] font-black text-slate-400 uppercase tracking-[0.25em] mb-1">
            <User class="w-3 h-3" />
            Creator
          </div>
          <div class="text-sm font-bold text-slate-100 leading-snug">{{ payload.creator }}</div>
        </div>

        <div
          v-if="payload?.copyright"
          class="p-3 rounded-xl bg-black/30 border border-white/5"
        >
          <div class="flex items-center gap-1.5 text-[9px] font-black text-slate-400 uppercase tracking-[0.25em] mb-1">
            <Copyright class="w-3 h-3" />
            Copyright
          </div>
          <div class="text-sm font-bold text-slate-100 leading-snug">{{ payload.copyright }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

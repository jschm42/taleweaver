<script setup lang="ts">
import type { Component } from 'vue'
import { AlertTriangle, CheckCircle2, Info, Sparkles, X, XCircle } from 'lucide-vue-next'
import { dismissToast, toastState, type ToastTone } from '@/composables/useToast'

/** Renders the app-wide toasts (bottom right). Mounted once in App.vue. */
const TONE: Record<ToastTone, { icon: Component; className: string }> = {
  success: { icon: CheckCircle2, className: 'text-wb-accent-text' },
  info: { icon: Info, className: 'text-wb-info-text' },
  warn: { icon: AlertTriangle, className: 'text-wb-warn-text' },
  error: { icon: XCircle, className: 'text-wb-danger-text' },
  ai: { icon: Sparkles, className: 'text-wb-ai-text' },
}
</script>

<template>
  <div class="pointer-events-none fixed bottom-4 right-4 z-[250] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2 font-wb" aria-live="polite">
    <TransitionGroup
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-2"
      leave-active-class="transition duration-150 ease-in"
      leave-to-class="opacity-0"
    >
      <div
        v-for="toast in toastState.items"
        :key="toast.id"
        :role="toast.tone === 'error' ? 'alert' : 'status'"
        class="pointer-events-auto flex items-start gap-3 rounded-xl border border-wb-line-strong bg-wb-overlay p-3 shadow-wb-float"
      >
        <component :is="TONE[toast.tone].icon" :class="['mt-0.5 h-4 w-4 shrink-0', TONE[toast.tone].className]" aria-hidden="true" />
        <div class="min-w-0 flex-1">
          <p v-if="toast.title" class="wb-subheading">{{ toast.title }}</p>
          <p class="wb-body text-wb-body break-words">{{ toast.message }}</p>
        </div>
        <button
          type="button"
          class="rounded-md p-0.5 text-wb-faint hover:text-wb-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
          aria-label="Dismiss"
          @click="dismissToast(toast.id)"
        >
          <X class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

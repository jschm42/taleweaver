<template>
  <header class="h-16 flex items-center justify-between px-10 border-b border-white/5 bg-[#050b14]/40 backdrop-blur-md z-40">
    <div class="flex-1 max-w-xl">
      <div class="relative group">
        <i class="ra ra-search absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-aether-primary transition-colors"></i>
        <input
          type="text"
          placeholder="Search your library..."
          class="w-full bg-aether-surface/40 border border-white/5 rounded-xl py-2 px-12 text-sm focus:outline-none focus:border-aether-primary/40 transition-all"
        />
      </div>
    </div>

    <div class="flex items-center gap-4"></div>
  </header>
</template>

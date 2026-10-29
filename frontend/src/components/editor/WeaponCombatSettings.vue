<script setup lang="ts">
import { computed } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import { AMOUNT_PATTERN, EFFECT_STATS, STAT_SHORT, SUCCESS_STATS } from '@/utils/specialAttacks'
import {
  DEFAULT_WEAPON_HIT_STAT,
  DICE_PATTERN,
  MAX_WEAPON_EFFECTS,
  WEAPON_CATEGORIES,
  WEAPON_CATEGORY_META,
  type WeaponConfig,
} from '@/utils/weaponConfig'

const config = defineModel<WeaponConfig>({ required: true })

const inputClass = 'w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-white font-bold focus:border-cyan-500/50 outline-none transition-all'
const diceValid = computed(() => DICE_PATTERN.test(config.value.damage_dice.replace(/\s/g, '')))

function addEffect(): void {
  if (config.value.effects.length >= MAX_WEAPON_EFFECTS) return
  config.value.effects.push({ target: 'target', stat: 'stamina', amount: '-1d4' })
}

function validAmount(amount: string): boolean {
  return AMOUNT_PATTERN.test(amount.replace(/\s/g, ''))
}
</script>

<template>
  <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Combat (Weapon Attack)</label>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <label class="space-y-1">
        <span class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Category</span>
        <select v-model="config.category" :class="inputClass">
          <option v-for="c in WEAPON_CATEGORIES" :key="c" :value="c">{{ WEAPON_CATEGORY_META[c].label }}</option>
        </select>
      </label>
      <label class="space-y-1">
        <span class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Attack roll stat</span>
        <select v-model="config.hit_stat" :class="inputClass">
          <option :value="null">{{ STAT_SHORT[DEFAULT_WEAPON_HIT_STAT] }} (default)</option>
          <option v-for="s in SUCCESS_STATS" :key="s" :value="s">{{ STAT_SHORT[s] }}</option>
        </select>
      </label>
      <label class="space-y-1">
        <span class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Damage (dice)</span>
        <input
          v-model="config.damage_dice"
          placeholder="1d8+1"
          :class="[inputClass, 'font-mono', diceValid ? '' : '!border-rose-500/70']"
        />
      </label>
      <div class="flex gap-2">
        <label class="space-y-1 flex-1">
          <span class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Cost per attack</span>
          <input v-model.number="config.cost_value" type="number" min="0" :class="inputClass" />
        </label>
        <label class="space-y-1 flex-1">
          <span class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Paid with</span>
          <select v-model="config.cost_type" :class="inputClass">
            <option value="stamina">Stamina</option>
            <option value="mana">Mana</option>
          </select>
        </label>
      </div>
    </div>

    <div class="space-y-1.5">
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Extra effects on hit</span>
        <button
          type="button"
          class="text-emerald-400 text-xs font-bold flex items-center gap-1 disabled:opacity-40"
          :disabled="config.effects.length >= MAX_WEAPON_EFFECTS"
          @click="addEffect"
        ><Plus class="w-3 h-3" /> Effect</button>
      </div>
      <div v-for="(eff, idx) in config.effects" :key="idx" class="flex items-center gap-2">
        <select v-model="eff.target" class="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-white text-xs">
          <option value="target">Target</option>
          <option value="self">Wielder</option>
        </select>
        <select v-model="eff.stat" class="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-white text-xs">
          <option v-for="s in EFFECT_STATS" :key="s" :value="s">{{ STAT_SHORT[s] }}</option>
        </select>
        <input
          v-model="eff.amount"
          placeholder="-1d4"
          class="w-28 bg-black/40 border rounded-lg px-2 py-1 text-white text-xs font-mono"
          :class="validAmount(eff.amount) ? 'border-white/5' : 'border-rose-500/70'"
        />
        <button type="button" class="p-1 text-slate-500 hover:text-rose-400" @click="config.effects.splice(idx, 1)"><Trash2 class="w-3.5 h-3.5" /></button>
      </div>
      <p class="text-[10px] text-slate-500">
        Applied in addition to the damage whenever the attack hits, e.g. poison (Target STA -1d4) or life drain (Wielder HP +2).
        Negative amounts drain, positive amounts boost; attribute changes last until the fight ends.
      </p>
    </div>
  </div>
</template>

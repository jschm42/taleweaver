/**
 * Deterministic syllable-based pseudo-name generator for procedural dynamic scenes.
 * Matches backend/engine/world/dynamic_pseudoname.py so editor previews and
 * server-side placeholders resolve identically.
 */

const BASE36_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

const ROOT_ONSETS = [
  'AL', 'AR', 'ASH', 'BEL', 'BRAN', 'CAL', 'COR', 'DAL',
  'DRA', 'DUN', 'EL', 'FAL', 'FEN', 'GAR', 'HAL', 'HEL',
  'JOR', 'KAEL', 'KEL', 'KETH', 'LOR', 'MAL', 'MAR', 'MOR',
  'NOR', 'OR', 'RAL', 'SOL', 'TAL', 'THAR', 'TOR', 'VAL',
  'VAR', 'VEL', 'VOR', 'ZAN',
] as const

const ROOT_CODAS = [
  'AN', 'AR', 'ATH', 'DOR', 'DRIS', 'EN', 'ER', 'ETH',
  'GAR', 'ION', 'IR', 'IS', 'ITH', 'KOR', 'MAR', 'MIR',
  'MON', 'MOR', 'NEN', 'NOR', 'ON', 'OR', 'OS', 'OTH',
  'RAK', 'RAN', 'REN', 'RIK', 'RIN', 'ROS', 'THAL', 'TOR',
  'VAN', 'VANE', 'VORN', 'WYN',
] as const

const SECOND_TOKENS = [
  'ASH', 'BANE', 'BARK', 'BRIM', 'CAIRN', 'CLEFT', 'CRAG', 'CREST',
  'DEEP', 'DELVE', 'DUSK', 'FANG', 'FELL', 'FEN', 'FOLD', 'FORGE',
  'GALE', 'GLADE', 'GLOOM', 'GRIM', 'HOLD', 'HOLLOW', 'KETH', 'MIRE',
  'MIST', 'MOOR', 'REACH', 'RIFT', 'RUIN', 'SHADE', 'SPIRE', 'THORN',
  'VALE', 'VAULT', 'VEIL', 'WARD',
] as const

const SHA256_K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
])

function rotr(value: number, bits: number): number {
  return (value >>> bits) | (value << (32 - bits))
}

function sha256Bytes(text: string): Uint8Array {
  const utf8 = new TextEncoder().encode(text)
  const bitLen = utf8.length * 8
  const paddedLen = Math.ceil((utf8.length + 9) / 64) * 64
  const padded = new Uint8Array(paddedLen)
  padded.set(utf8)
  padded[utf8.length] = 0x80

  const view = new DataView(padded.buffer)
  view.setUint32(paddedLen - 8, Math.floor(bitLen / 0x100000000), false)
  view.setUint32(paddedLen - 4, bitLen >>> 0, false)

  let h0 = 0x6a09e667
  let h1 = 0xbb67ae85
  let h2 = 0x3c6ef372
  let h3 = 0xa54ff53a
  let h4 = 0x510e527f
  let h5 = 0x9b05688c
  let h6 = 0x1f83d9ab
  let h7 = 0x5be0cd19

  const w = new Uint32Array(64)

  for (let offset = 0; offset < paddedLen; offset += 64) {
    for (let i = 0; i < 16; i += 1) {
      w[i] = view.getUint32(offset + i * 4, false)
    }
    for (let i = 16; i < 64; i += 1) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3)
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10)
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0
    }

    let a = h0
    let b = h1
    let c = h2
    let d = h3
    let e = h4
    let f = h5
    let g = h6
    let h = h7

    for (let i = 0; i < 64; i += 1) {
      const s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
      const ch = (e & f) ^ (~e & g)
      const temp1 = (h + s1 + ch + SHA256_K[i] + w[i]) >>> 0
      const s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
      const maj = (a & b) ^ (a & c) ^ (b & c)
      const temp2 = (s0 + maj) >>> 0

      h = g
      g = f
      f = e
      e = (d + temp1) >>> 0
      d = c
      c = b
      b = a
      a = (temp1 + temp2) >>> 0
    }

    h0 = (h0 + a) >>> 0
    h1 = (h1 + b) >>> 0
    h2 = (h2 + c) >>> 0
    h3 = (h3 + d) >>> 0
    h4 = (h4 + e) >>> 0
    h5 = (h5 + f) >>> 0
    h6 = (h6 + g) >>> 0
    h7 = (h7 + h) >>> 0
  }

  const out = new Uint8Array(32)
  const outView = new DataView(out.buffer)
  outView.setUint32(0, h0, false)
  outView.setUint32(4, h1, false)
  outView.setUint32(8, h2, false)
  outView.setUint32(12, h3, false)
  outView.setUint32(16, h4, false)
  outView.setUint32(20, h5, false)
  outView.setUint32(24, h6, false)
  outView.setUint32(28, h7, false)
  return out
}

function normalizeSeedToken(raw: unknown, fallback = 'ZONE', maxLen = 24): string {
  const cleaned = String(raw || '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return (cleaned || fallback).slice(0, maxLen)
}

export function generateDeterministicPseudoname(seedText: string, maxLen = 16): string {
  const safeMax = Math.max(4, Math.floor(maxLen || 16))
  const digest = sha256Bytes(String(seedText || 'DYNAMIC'))

  const onset = ROOT_ONSETS[digest[0] % ROOT_ONSETS.length]
  const coda = ROOT_CODAS[digest[1] % ROOT_CODAS.length]
  const second = SECOND_TOKENS[digest[2] % SECOND_TOKENS.length]
  const tagA = BASE36_ALPHABET[digest[3] % BASE36_ALPHABET.length]
  const tagB = BASE36_ALPHABET[digest[4] % BASE36_ALPHABET.length]

  const firstWord = `${onset}${coda}`.slice(0, 7)
  const secondWord = `${second.slice(0, 4)}${tagA}${tagB}`
  const combined = `${firstWord}_${secondWord}`
  if (combined.length <= safeMax) return combined
  const trimmed = combined.slice(0, safeMax).replace(/_+$/g, '')
  return trimmed || firstWord.slice(0, safeMax)
}

export function buildDynamicPlaceholderSceneId(
  zoneId: string,
  depth = 1,
  index = 1,
  suffix = '',
): string {
  const normZone = normalizeSeedToken(zoneId, 'ZONE', 24)
  const safeDepth = Math.max(1, Math.floor(Number(depth) || 1))
  const safeIndex = Math.max(1, Math.floor(Number(index) || 1))
  const normSuffix = String(suffix || '')
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '')
    .slice(0, 8)
  const seedText = `${normZone}:D${safeDepth}:I${safeIndex}:S${normSuffix}`
  const pseudo = generateDeterministicPseudoname(seedText, 16)
  return `DYN_${pseudo}`.slice(0, 20).replace(/_+$/g, '')
}

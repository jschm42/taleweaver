import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { Buffer } from 'node:buffer'
import ts from 'typescript'

const filename = new URL('../src/components/portal/leaderboard/leaderboardUtils.ts', import.meta.url)
const source = ts.transpileModule(readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
}).outputText
const { sortPlayers, filterPlayers, rankTier, normalizeAvatarUrl, playerAvatarUrl, formatNumber } =
  await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)

const player = (rank, username, awards, completed, failed) => ({
  rank, username, total_awards: awards, completed_quests: completed, failed_quests: failed
})

const players = [
  player(3, 'Cassandra', 5, 2, 4),
  player(1, 'aldric', 2, 9, 0),
  player(2, 'Bram', 5, 4, 1),
  player(4, 'dorian', 0, 4, 1),
]
const usernames = list => list.map(p => p.username)

test('sortPlayers orders by server rank ascending', () => {
  assert.deepEqual(usernames(sortPlayers(players, 'rank')), ['aldric', 'Bram', 'Cassandra', 'dorian'])
})

test('sortPlayers orders stat keys descending and breaks ties by rank', () => {
  assert.deepEqual(usernames(sortPlayers(players, 'awards')), ['Bram', 'Cassandra', 'aldric', 'dorian'])
  assert.deepEqual(usernames(sortPlayers(players, 'completed')), ['aldric', 'Bram', 'dorian', 'Cassandra'])
  assert.deepEqual(usernames(sortPlayers(players, 'failed')), ['Cassandra', 'Bram', 'dorian', 'aldric'])
})

test('sortPlayers does not mutate the input array', () => {
  const before = [...players]
  sortPlayers(players, 'awards')
  assert.deepEqual(players, before)
})

test('filterPlayers matches usernames case-insensitively on a trimmed query', () => {
  assert.deepEqual(usernames(filterPlayers(players, '  BR ')), ['Bram'])
  assert.deepEqual(usernames(filterPlayers(players, 'DR')), ['Cassandra', 'aldric'])
  assert.deepEqual(filterPlayers(players, 'zzz'), [])
})

test('filterPlayers returns the original list for a blank query', () => {
  assert.equal(filterPlayers(players, ''), players)
  assert.equal(filterPlayers(players, '   '), players)
})

test('rankTier maps the podium ranks and falls back to plain', () => {
  assert.equal(rankTier(1), 'gold')
  assert.equal(rankTier(2), 'silver')
  assert.equal(rankTier(3), 'bronze')
  assert.equal(rankTier(4), 'plain')
  assert.equal(rankTier(0), 'plain')
})

test('normalizeAvatarUrl converts backslashes and tolerates missing values', () => {
  assert.equal(normalizeAvatarUrl('static\\avatars\\a.png'), 'static/avatars/a.png')
  assert.equal(normalizeAvatarUrl('/static/avatars/b.png'), '/static/avatars/b.png')
  assert.equal(normalizeAvatarUrl(null), '')
  assert.equal(normalizeAvatarUrl(undefined), '')
  assert.equal(normalizeAvatarUrl(''), '')
})

test('playerAvatarUrl keeps a profile image and falls back to the generated avatar', () => {
  assert.equal(playerAvatarUrl('static\\avatars\\a.png', 'admin'), 'static/avatars/a.png')
  assert.equal(playerAvatarUrl(null, 'admin'), 'https://api.dicebear.com/7.x/avataaars/svg?seed=admin')
  assert.equal(playerAvatarUrl('', 'Sir Bram'), 'https://api.dicebear.com/7.x/avataaars/svg?seed=Sir%20Bram')
})

test('formatNumber uses en-US grouping', () => {
  assert.equal(formatNumber(0), '0')
  assert.equal(formatNumber(999), '999')
  assert.equal(formatNumber(1234567), '1,234,567')
  assert.equal(formatNumber(-4200), '-4,200')
})

const API_BASE = 'http://localhost:8000'

export async function uploadMatch(title, file, playedOn) {
  const form = new FormData()
  form.append('title', title)
  if (playedOn) form.append('played_on', playedOn)
  form.append('file', file)
  const res = await fetch(`${API_BASE}/matches`, { method: 'POST', body: form })
  return jsonOrThrow(res, 'Failed to upload match')
}

export async function listMatches() {
  const res = await fetch(`${API_BASE}/matches`)
  return jsonOrThrow(res, 'Failed to load matches')
}

export async function listRallies(matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/rallies`)
  return jsonOrThrow(res, 'Failed to load rallies')
}

// rally = { start, end, outcome, skills?, player?, notes? }. The clip is cut automatically.
export async function createRally(matchId, rally) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/rallies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rally),
  })
  return jsonOrThrow(res, 'Failed to save rally')
}

export async function reclip(rallyId) {
  const res = await fetch(`${API_BASE}/rallies/${rallyId}/reclip`, { method: 'POST' })
  return jsonOrThrow(res, 'Failed to re-cut clip')
}

export async function deleteRally(rallyId) {
  const res = await fetch(`${API_BASE}/rallies/${rallyId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete rally')
}

// filters = { title?, outcomes?, skills?, match_ids?, player?, highlights_only?, clip_ids? }
export async function createReel(filters) {
  const res = await fetch(`${API_BASE}/reels`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(filters),
  })
  return jsonOrThrow(res, 'Failed to build highlight reel')
}

// The API returns media as server-relative URLs (/media/...).
export function mediaUrl(url) {
  return url ? `${API_BASE}${url}` : null
}

// --- Automatic highlight detection ---------------------------------------

async function jsonOrThrow(res, fallback) {
  if (res.ok) return res.json()
  let detail = fallback
  try {
    detail = (await res.json()).detail ?? fallback
  } catch {
    // keep the fallback message
  }
  throw new Error(typeof detail === 'string' ? detail : fallback)
}

export async function startAnalysis(matchId, settings = {}) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/analysis/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ settings }),
  })
  return jsonOrThrow(res, 'Failed to start analysis')
}

// Resolves to null if the match has never been analysed.
export async function getAnalysis(matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/analysis/`)
  if (res.status === 404) return null
  return jsonOrThrow(res, 'Failed to load analysis')
}

export async function deleteHighlight(matchId, highlightId) {
  const res = await fetch(
    `${API_BASE}/matches/${matchId}/analysis/highlights/${highlightId}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error('Failed to remove highlight')
}

export async function renderAutoReel(matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/analysis/reel/render`, {
    method: 'POST',
  })
  return jsonOrThrow(res, 'Failed to render reel')
}

export function formatTime(seconds) {
  const s = Math.max(0, Math.round(seconds * 10) / 10)
  const m = Math.floor(s / 60)
  return `${m}:${(s - m * 60).toFixed(1).padStart(4, '0')}`
}

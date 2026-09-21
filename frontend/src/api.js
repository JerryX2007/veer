const API_BASE = 'http://localhost:8000'

export async function uploadMatch(title, file) {
  const form = new FormData()
  form.append('title', title)
  form.append('file', file)
  const res = await fetch(`${API_BASE}/matches/`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('Failed to upload match')
  return res.json()
}

export async function listMatches() {
  const res = await fetch(`${API_BASE}/matches/`)
  return res.json()
}

export async function listRallies(matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/rallies/`)
  return res.json()
}

export async function createRally(matchId, rally) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/rallies/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rally),
  })
  if (!res.ok) throw new Error('Failed to save rally')
  return res.json()
}

export async function exportClip(matchId, rallyId) {
  const res = await fetch(
    `${API_BASE}/matches/${matchId}/rallies/${rallyId}/export-clip`,
    { method: 'POST' },
  )
  if (!res.ok) throw new Error('Failed to export clip')
  return res.json()
}

export async function buildHighlightReel(matchId, outcomes) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/highlight-reel/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outcomes }),
  })
  if (!res.ok) throw new Error('Failed to build highlight reel')
  return res.json()
}

export function videoUrl(relativePath) {
  return `${API_BASE}/${relativePath}`
}

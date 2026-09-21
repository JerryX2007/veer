import { useState } from 'react'
import { uploadMatch } from '../api.js'

export default function UploadMatch({ onUploaded }) {
  const [title, setTitle] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title || !file) return
    setBusy(true)
    try {
      await uploadMatch(title, file)
      setTitle('')
      setFile(null)
      onUploaded()
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ marginBottom: '2rem' }}>
      <h2>Upload a match</h2>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Title (e.g. Practice 9/20)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <input
          type="file"
          accept="video/*"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button type="submit" disabled={busy || !title || !file}>
          {busy ? 'Uploading…' : 'Upload'}
        </button>
      </div>
    </form>
  )
}

import { useEffect, useState } from 'react'
import UploadMatch from './components/UploadMatch.jsx'
import RallyTagger from './components/RallyTagger.jsx'
import { listMatches } from './api.js'

export default function App() {
  const [matches, setMatches] = useState([])
  const [selectedMatch, setSelectedMatch] = useState(null)

  const refreshMatches = async () => {
    const data = await listMatches()
    setMatches(data)
  }

  useEffect(() => {
    refreshMatches()
  }, [])

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem' }}>
      <h1>Volleyball rally tagger</h1>

      <UploadMatch onUploaded={refreshMatches} />

      <h2>Your matches</h2>
      {matches.length === 0 && <p>No matches uploaded yet.</p>}
      <ul style={{ paddingLeft: '1.2rem' }}>
        {matches.map((m) => (
          <li key={m.id}>
            <button onClick={() => setSelectedMatch(m)}>{m.title}</button>
          </li>
        ))}
      </ul>

      {selectedMatch && <RallyTagger match={selectedMatch} />}
    </div>
  )
}

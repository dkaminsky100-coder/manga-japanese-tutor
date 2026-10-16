import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteChapter, listChapters, uploadChapter, type ChapterSummary } from '../api/client'

export default function Library() {
  const [chapters, setChapters] = useState<ChapterSummary[]>([])
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const refresh = useCallback(() => {
    listChapters().then(setChapters).catch((e) => setError(e.message))
  }, [])

  useEffect(refresh, [refresh])

  async function onUpload(e: React.FormEvent) {
    e.preventDefault()
    const files = Array.from(fileInput.current?.files ?? [])
    if (!files.length) return
    setBusy(true)
    setError(null)
    try {
      await uploadChapter(title, files)
      setTitle('')
      if (fileInput.current) fileInput.current.value = ''
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  async function onDelete(id: number) {
    if (!window.confirm('Delete this chapter?')) return
    await deleteChapter(id).catch((e) => setError(e.message))
    refresh()
  }

  return (
    <main className="library">
      <h1>Manga Japanese Tutor</h1>
      <form onSubmit={onUpload} className="upload">
        <input placeholder="Title (optional)" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input ref={fileInput} type="file" multiple accept="image/*,.cbz,.zip,.pdf" required />
        <button disabled={busy}>{busy ? 'Uploading…' : 'Upload chapter'}</button>
      </form>
      {error && <p className="error">{error}</p>}
      <ul className="chapters">
        {chapters.map((c) => (
          <li key={c.id}>
            <Link to={`/read/${c.id}`}>{c.title}</Link>
            <span>{c.page_count} pages</span>
            <button onClick={() => onDelete(c.id)}>Delete</button>
          </li>
        ))}
        {!chapters.length && <li className="empty">No chapters yet — upload images, a .cbz or a PDF.</li>}
      </ul>
    </main>
  )
}

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getChapter, pageImageUrl, type Chapter } from '../api/client'

export default function Reader() {
  const id = Number(useParams().chapterId)
  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [index, setIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getChapter(id).then(setChapter).catch((e) => setError(e.message))
  }, [id])

  const last = (chapter?.pages.length ?? 1) - 1
  // Manga reads right-to-left: ArrowLeft advances, ArrowRight goes back.
  const next = () => setIndex((i) => Math.min(i + 1, last))
  const prev = () => setIndex((i) => Math.max(i - 1, 0))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') next()
      else if (e.key === 'ArrowRight') prev()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (error) return <p className="error">{error}</p>
  if (!chapter) return <p>Loading…</p>
  const page = chapter.pages[index]

  return (
    <div className="reader">
      <header>
        <Link to="/">← Library</Link>
        <strong>{chapter.title}</strong>
        <span>
          <button onClick={next} disabled={index >= last}>◀ Next</button>
          {index + 1} / {chapter.pages.length}
          <button onClick={prev} disabled={index === 0}>Prev ▶</button>
        </span>
      </header>
      <div className="page">
        <img key={page.id} src={pageImageUrl(page.id)} width={page.width} height={page.height} alt={`Page ${index + 1}`} />
      </div>
    </div>
  )
}

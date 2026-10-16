import type { RubySegment } from '../api/client'

/** Text with furigana: <ruby> over kanji segments, plain text for kana. */
export default function Ruby({ segments }: { segments: RubySegment[] }) {
  return (
    <>
      {segments.map((s, i) =>
        s.ruby ? (
          <ruby key={i}>
            {s.text}
            <rp>(</rp>
            <rt>{s.ruby}</rt>
            <rp>)</rp>
          </ruby>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </>
  )
}

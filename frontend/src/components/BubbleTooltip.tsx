import type { Compound, DictEntry, GrammarUnit, TextBlock, TranslationState, WordToken } from '../api/client'
import Ruby from './Ruby'

const MAX_SENSES_SHOWN = 3

function headword(e: DictEntry): string {
  return e.kanji[0] ?? e.kana[0]
}

/** "1. to eat  2. to live on; to live off" for the first few senses of an entry. */
function Senses({ entry }: { entry: DictEntry }) {
  const shown = entry.senses.slice(0, MAX_SENSES_SHOWN)
  const hidden = entry.senses.length - shown.length + entry.more_senses
  return (
    <ol className="senses">
      {shown.map((s, i) => (
        <li key={i}>
          {s.pos.length > 0 && i === 0 && <span className="pos">{s.pos.join(', ')} · </span>}
          {s.glosses.join('; ')}
        </li>
      ))}
      {hidden > 0 && <li className="more">+{hidden} more senses</li>}
    </ol>
  )
}

function Entry({ entry }: { entry: DictEntry }) {
  const reading = entry.kanji.length > 0 ? entry.kana[0] : null
  return (
    <div className="entry">
      <div className="entry-head">
        <strong lang="ja">{headword(entry)}</strong>
        {reading && <span lang="ja"> 【{reading}】</span>}
        {entry.common && <span className="badge">common</span>}
      </div>
      <Senses entry={entry} />
    </div>
  )
}

function Entries({ entries }: { entries: DictEntry[] }) {
  const [first, ...rest] = entries
  return (
    <>
      <Entry entry={first} />
      {rest.length > 0 && (
        <details className="other-entries">
          <summary>
            {rest.length} other {rest.length === 1 ? 'entry' : 'entries'}
          </summary>
          {rest.map((e) => (
            <Entry key={e.id} entry={e} />
          ))}
        </details>
      )}
    </>
  )
}

function Word({ token }: { token: WordToken }) {
  return (
    <li className="word">
      <div className="word-head">
        <span className="word-surface" lang="ja">
          <Ruby segments={token.ruby} />
        </span>
        <span className="pos-tag">{token.particle_kind || token.pos_label}</span>
        {token.verb_class && <span className="pos-tag">{token.verb_class}</span>}
        {token.dictionary_form !== token.surface && (
          <span className="base-form" lang="ja">
            ← {token.dictionary_form}
          </span>
        )}
        {token.conj_label && (
          <span className="inflection" title={token.conj_form}>
            {token.conj_label}
          </span>
        )}
      </div>
      {token.note && <p className="particle-note">{token.note}</p>}
      {token.entries.length > 0 ? (
        <Entries entries={token.entries} />
      ) : (
        <p className="no-entry">No dictionary entry found.</p>
      )}
    </li>
  )
}

function Phrases({ compounds }: { compounds: Compound[] }) {
  if (compounds.length === 0) return null
  return (
    <section className="phrases">
      <h4>Phrases</h4>
      {compounds.map((c) => (
        <div key={`${c.start}-${c.end}`} className="phrase">
          <Entries entries={c.entries} />
        </div>
      ))}
    </section>
  )
}

/** Predicate chains: a verb / adjective with its auxiliaries, explained step by step. */
function Grammar({ units, tokens }: { units: GrammarUnit[]; tokens: WordToken[] }) {
  if (units.length === 0) return null
  return (
    <section className="grammar">
      <h4>Grammar</h4>
      {units.map((u) => (
        <div key={`${u.start}-${u.end}`} className="unit">
          <div className="unit-head">
            <span className="unit-text" lang="ja">
              {tokens.slice(u.start, u.end).map((t, i) => (
                <Ruby key={i} segments={t.ruby} />
              ))}
            </span>
            <span className="unit-summary">{u.summary}</span>
          </div>
          <ol className="steps">
            {u.steps.map((st, i) => (
              <li key={i}>
                <span className="step-text" lang="ja">
                  {st.text}
                </span>{' '}
                <strong>{st.label}</strong>
                {st.note && <span className="step-note"> — {st.note}</span>}
              </li>
            ))}
          </ol>
        </div>
      ))}
    </section>
  )
}

function Translate({ state, onTranslate }: { state: TranslationState; onTranslate: () => void }) {
  switch (state.status) {
    case 'idle':
      return (
        <button type="button" className="translate-btn" onClick={onTranslate}>
          Translate
        </button>
      )
    case 'loading':
      return <p className="translation-status">Translating…</p>
    case 'error':
      return (
        <p className="translation-status error">
          {state.message}{' '}
          <button type="button" className="translate-btn" onClick={onTranslate}>
            Try again
          </button>
        </p>
      )
    case 'done':
      return (
        <div className="translation">
          <p className="translation-text">{state.text || '(no translation)'}</p>
          <p className="translation-note">Rough machine translation · may be wrong, especially for slang</p>
        </div>
      )
  }
}

interface Props {
  block: TextBlock
  pinned: boolean
  translation: TranslationState
  onTranslate: () => void
}

/** Tooltip body: the sentence with furigana, a translation on demand, phrases, then a word-by-word breakdown. */
export default function BubbleTooltip({ block, pinned, translation, onTranslate }: Props) {
  const words = block.tokens.filter((t) => t.pos_label !== 'symbol' && t.pos_label !== 'space')
  return (
    <div className="tooltip" role="tooltip">
      <p className="tooltip-text" lang="ja">
        {block.tokens.length > 0
          ? block.tokens.map((t, i) => <Ruby key={i} segments={t.ruby} />)
          : block.text}
      </p>
      <Translate state={translation} onTranslate={onTranslate} />
      <Grammar units={block.grammar} tokens={block.tokens} />
      <Phrases compounds={block.compounds} />
      {words.length > 0 && (
        <ul className="words">
          {words.map((t, i) => (
            <Word key={i} token={t} />
          ))}
        </ul>
      )}
      <p className="tooltip-hint">{pinned ? 'Pinned · click the bubble or press Esc to close' : 'Click to pin'}</p>
    </div>
  )
}

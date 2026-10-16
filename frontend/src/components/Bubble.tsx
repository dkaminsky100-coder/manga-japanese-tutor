import { useState } from 'react'
import {
  FloatingPortal,
  autoUpdate,
  flip,
  offset,
  safePolygon,
  shift,
  size,
  useDismiss,
  useFloating,
  useHover,
  useInteractions,
  type OpenChangeReason,
} from '@floating-ui/react'
import { editBlock, revertBlock, translateBlock, type TextBlock, type TranslationState } from '../api/client'
import type { PercentRect } from '../lib/coords'
import { fitToAvailable, VIEWPORT_PADDING } from '../lib/layout'
import BubbleTooltip from './BubbleTooltip'

interface Props {
  block: TextBlock
  rect: PercentRect
  /** 1-based position, shown only in the debug view */
  label: number | null
  /** Called with the updated block after the user corrects (or resets) its text */
  onChange: (block: TextBlock) => void
}

const IDLE: TranslationState = { status: 'idle' }
const errorMessage = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback)

/**
 * One detected text block: an invisible hit-box over the page that shows a tooltip on
 * hover and keeps it open ("pins" it) when clicked. The tooltip also lets the user correct
 * the OCR text.
 */
export default function Bubble({ block, rect, label, onChange }: Props) {
  const [hoverOpen, setHoverOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const open = hoverOpen || pinned

  // Kept here, not in the tooltip, so a translation survives the tooltip closing and reopening.
  // It is tied to the text it translated: after the text is corrected the old translation no
  // longer applies (and comes back if the correction is undone).
  const [slot, setSlot] = useState<{ forText: string; state: TranslationState }>({ forText: block.text, state: IDLE })
  const translation = slot.forText === block.text ? slot.state : IDLE

  function translate() {
    if (translation.status === 'loading') return
    const text = block.text
    setSlot({ forText: text, state: { status: 'loading' } })
    const finish = (state: TranslationState) => setSlot((cur) => (cur.forText === text ? { forText: text, state } : cur))
    translateBlock(block.id)
      .then((r) => finish({ status: 'done', text: r.translation }))
      .catch((e) => finish({ status: 'error', message: errorMessage(e, 'Translation failed') }))
  }

  function startEdit() {
    setEditError(null)
    setEditing(true)
    setPinned(true) // keep the tooltip open while typing, even if the pointer leaves
  }

  function cancelEdit() {
    setEditing(false)
    setEditError(null)
  }

  async function save(text: string) {
    if (text.replace(/\s+/g, '') === block.text) return cancelEdit() // nothing changed
    setSaving(true)
    setEditError(null)
    try {
      onChange(await editBlock(block.id, text))
      setEditing(false)
    } catch (e) {
      setEditError(errorMessage(e, 'Could not save'))
    } finally {
      setSaving(false)
    }
  }

  async function revert() {
    setSaving(true)
    setEditError(null)
    try {
      onChange(await revertBlock(block.id))
    } catch (e) {
      setEditError(errorMessage(e, 'Could not reset'))
    } finally {
      setSaving(false)
    }
  }

  const { refs, floatingStyles, context } = useFloating({
    open,
    onOpenChange: (next: boolean, _event?: Event, reason?: OpenChangeReason) => {
      setHoverOpen(next)
      // Moving the mouse away (reasons 'hover' / 'safe-polygon') only closes a hover;
      // Escape or clicking elsewhere also unpins.
      if (!next && (reason === 'escape-key' || reason === 'outside-press')) setPinned(false)
    },
    placement: 'bottom',
    middleware: [
      offset(8),
      // Pick the side (above/below) with more room when neither fits the whole tooltip...
      flip({ padding: VIEWPORT_PADDING, fallbackStrategy: 'bestFit' }),
      // ...then cap its size to that room; the tooltip scrolls inside instead of being cut off.
      size({
        padding: VIEWPORT_PADDING,
        apply({ availableWidth, availableHeight, elements }) {
          Object.assign(elements.floating.style, fitToAvailable(availableWidth, availableHeight))
        },
      }),
      shift({ padding: VIEWPORT_PADDING }),
    ],
    whileElementsMounted: autoUpdate,
  })

  const hover = useHover(context, { handleClose: safePolygon(), delay: { open: 60, close: 120 } })
  // While editing, only Save / Cancel end the edit: a stray click or Escape must not throw away typing.
  const dismiss = useDismiss(context, { escapeKey: !editing, outsidePress: !editing })
  const { getReferenceProps, getFloatingProps } = useInteractions([hover, dismiss])

  return (
    <>
      <div
        ref={refs.setReference}
        className={`block-box${label !== null ? ' debug' : ''}${open ? ' active' : ''}${pinned ? ' pinned' : ''}`}
        style={{ left: `${rect.left}%`, top: `${rect.top}%`, width: `${rect.width}%`, height: `${rect.height}%` }}
        {...getReferenceProps({ onClick: () => !editing && setPinned((p) => !p) })}
      >
        {label !== null && <span className="block-label">{label}</span>}
      </div>
      {open && (
        <FloatingPortal>
          <div ref={refs.setFloating} style={floatingStyles} className="tooltip-wrap" {...getFloatingProps()}>
            <BubbleTooltip
              block={block}
              pinned={pinned}
              translation={translation}
              onTranslate={translate}
              editor={{ editing, saving, error: editError, onStart: startEdit, onCancel: cancelEdit, onSave: save, onRevert: revert }}
            />
          </div>
        </FloatingPortal>
      )}
    </>
  )
}

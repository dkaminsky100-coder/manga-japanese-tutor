const TEXT_INPUT_TYPES = new Set(['text', 'search', 'url', 'email', 'password', 'number', 'tel', ''])

/**
 * True when keystrokes are going into a text field (or other editable element), so global
 * shortcuts such as the reader's arrow-key page turning must stay out of the way.
 * Checkboxes, buttons and the like are not text fields: the arrows should still turn pages
 * after you tick the "Boxes" box.
 */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable || target.getAttribute('contenteditable') === 'true') return true
  if (target instanceof HTMLTextAreaElement) return true
  if (target instanceof HTMLInputElement) return TEXT_INPUT_TYPES.has(target.type)
  return false
}

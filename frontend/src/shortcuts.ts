/**
 * Keyboard shortcut registration and keydown listener.
 *
 * Uses event.code (physical key position) for reliable matching
 * regardless of keyboard layout. Calls preventDefault() to suppress
 * browser defaults (e.g. F3 = Find in Chrome).
 */

type ShortcutHandler = () => void | Promise<void>;

const shortcuts: Record<string, ShortcutHandler> = {};

/**
 * Register a keyboard shortcut.
 * @param code - KeyboardEvent.code value (e.g. 'F2', 'Escape')
 * @param handler - Function to call when the key is pressed
 */
export function registerShortcut(code: string, handler: ShortcutHandler): void {
  shortcuts[code] = handler;
}

/**
 * Attach a single keydown listener that dispatches to registered shortcuts.
 * Call once on DOMContentLoaded after all shortcuts are registered.
 */
export function initShortcuts(): void {
  document.addEventListener('keydown', (event: KeyboardEvent) => {
    const handler = shortcuts[event.code];
    if (handler) {
      event.preventDefault();
      handler();
    }
  });
}

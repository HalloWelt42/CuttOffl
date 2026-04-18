// Ordner-Picker als Promise-basiertes Overlay.
// Lädt den Ordnerbaum über /api/folders und lässt den User einen
// bestehenden Ordner oder die Basis (oberste Ebene) wählen.
// Neuanlegen per Eingabe.

let _resolve = null;

export const folderPicker = $state({
  open: false,
  title: 'Ordner wählen',
  currentPath: '',
  // Für die Vormerkung während der Auswahl
  selected: '',
});

export function openFolderPicker(opts = {}) {
  Object.assign(folderPicker, {
    open: true,
    title: opts.title ?? 'Ordner wählen',
    currentPath: opts.current ?? '',
    selected:    opts.current ?? '',
  });
  return new Promise((res) => { _resolve = res; });
}

export function pickerOk() {
  if (!_resolve) return;
  _resolve(folderPicker.selected);
  _resolve = null;
  folderPicker.open = false;
}

export function pickerCancel() {
  if (!_resolve) return;
  _resolve(null);
  _resolve = null;
  folderPicker.open = false;
}

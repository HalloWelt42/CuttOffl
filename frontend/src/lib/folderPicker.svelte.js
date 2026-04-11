// Ordner-Picker als Promise-basiertes Overlay.
// Laedt den Ordnerbaum ueber /api/folders und laesst den User einen
// bestehenden Ordner oder die Wurzel waehlen. Neuanlegen per Eingabe.

let _resolve = null;

export const folderPicker = $state({
  open: false,
  title: 'Ordner wählen',
  currentPath: '',
  // Fuer die Vormerkung waehrend der Auswahl
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

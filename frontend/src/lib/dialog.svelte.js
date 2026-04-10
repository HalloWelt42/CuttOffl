// Eigener Dialog-Service -- ersetzt native prompt()/confirm()/alert().
// Gibt Promises zurueck, aufloesend nach Klick oder Esc/Enter.

let _resolve = null;

export const dialog = $state({
  open: false,
  kind: 'confirm',        // 'confirm' | 'prompt' | 'alert'
  title: '',
  message: '',
  value: '',              // Vorbelegung fuer prompt
  placeholder: '',
  okLabel: 'OK',
  cancelLabel: 'Abbrechen',
  okVariant: 'primary',   // 'primary' | 'danger'
});

function _open(cfg) {
  Object.assign(dialog, {
    open: true,
    kind: 'confirm',
    title: '',
    message: '',
    value: '',
    placeholder: '',
    okLabel: 'OK',
    cancelLabel: 'Abbrechen',
    okVariant: 'primary',
    ...cfg,
  });
  return new Promise((res) => { _resolve = res; });
}

export function confirmDialog(message, opts = {}) {
  return _open({
    kind: 'confirm',
    title: opts.title ?? 'Bitte bestätigen',
    message,
    okLabel: opts.okLabel ?? 'OK',
    cancelLabel: opts.cancelLabel ?? 'Abbrechen',
    okVariant: opts.okVariant ?? 'primary',
  });
}

export function promptDialog(message, defaultValue = '', opts = {}) {
  return _open({
    kind: 'prompt',
    title: opts.title ?? 'Eingabe',
    message,
    value: defaultValue,
    placeholder: opts.placeholder ?? '',
    okLabel: opts.okLabel ?? 'OK',
    cancelLabel: opts.cancelLabel ?? 'Abbrechen',
    okVariant: opts.okVariant ?? 'primary',
  });
}

export function alertDialog(message, opts = {}) {
  return _open({
    kind: 'alert',
    title: opts.title ?? 'Hinweis',
    message,
    okLabel: opts.okLabel ?? 'OK',
    cancelLabel: '',
  });
}

export function dialogOk() {
  if (!_resolve) return;
  const r = dialog.kind === 'prompt' ? (dialog.value ?? '') :
            dialog.kind === 'alert'  ? true : true;
  _resolve(r);
  _resolve = null;
  dialog.open = false;
}

export function dialogCancel() {
  if (!_resolve) return;
  const r = dialog.kind === 'prompt' ? null :
            dialog.kind === 'alert'  ? false : false;
  _resolve(r);
  _resolve = null;
  dialog.open = false;
}

// Fluechtiger UI-State (nicht persistiert): Overlays, Dialoge.

export const ui = $state({
  thanksOpen: false,
});

export function openThanks()  { ui.thanksOpen = true; }
export function closeThanks() { ui.thanksOpen = false; }

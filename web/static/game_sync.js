// Keep the game/server picker aligned across every open All for Cabal tab.
// The tab that writes localStorage does not receive its own storage event; its
// existing change handler already owns the local update. Other tabs receive
// the event here and replay a real change so their page-specific state follows.
(() => {
  const key = 'afc.game';

  window.addEventListener('storage', event => {
    if (event.storageArea !== localStorage || event.key !== key) return;
    const game = String(event.newValue || '');
    const picker = document.getElementById('game');
    if (!game || !picker || picker.value === game) return;
    if (![...picker.options].some(option => option.value === game)) return;
    picker.value = game;
    picker.dispatchEvent(new Event('change', {bubbles: true}));
  });
})();

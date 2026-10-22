import { loadCatalog, loadAsset } from './data/catalog.js';
import { createSelectionStore, selectionFromHash, selectionQuery } from './state/selection.js';

export function createExplorerRuntime(root, onSelection) {
  let query = location.hash.split('?')[1] || '', store, contextPromise;
  const slots = [...root.querySelectorAll('[data-explorer-component]')].map(element => ({ element, active: false, revision: 0, cleanup: null }));
  const context = () => {
    if (!contextPromise) contextPromise = loadCatalog().then(catalog => {
      store = createSelectionStore(catalog, selectionFromHash(`#?${query}`));
      if (!query) store.set(catalog.default_selection, { replace: true, history: false });
      store.subscribe(({ selection }, { history }) => { query = selectionQuery(selection); if (history) onSelection(query); });
      return { catalog, store, loadAsset };
    }).catch(error => { contextPromise = null; throw error; });
    return contextPromise;
  };
  const activate = async slot => {
    if (slot.active) return;
    slot.active = true; const revision = ++slot.revision;
    try {
      const api = await context();
      const module = slot.element.dataset.explorerComponent === 'place' ? await import('./components/place-explorer.js') : slot.element.dataset.explorerComponent === 'cohort' ? await import('./components/cohort-context.js') : slot.element.dataset.explorerComponent === 'scanner-regions' ? await import('./components/scanner-regions.js') : await import('./components/pathway-chart.js');
      if (!slot.active || revision !== slot.revision) return;
      const mount = module.mountPlaceExplorer || module.mountCohortContext || module.mountScannerRegions || module.mountPathwayChart;
      slot.cleanup = mount(slot.element, api);
    } catch (error) {
      if (!slot.active || revision !== slot.revision) return;
      slot.element.replaceChildren();
      const message = document.createElement('p'); message.className = 'notice'; message.textContent = error.message;
      const retry = document.createElement('button'); retry.textContent = 'Load place evidence'; retry.onclick = () => { slot.active = false; activate(slot); };
      slot.element.append(message, retry);
    }
  };
  const deactivate = slot => { if (!slot.active) return; slot.active = false; ++slot.revision; slot.cleanup?.(); slot.cleanup = null; };
  const refresh = () => slots.forEach(slot => {
    const box = slot.element.getBoundingClientRect();
    const visible = slot.element.getClientRects().length && box.bottom > 0 && box.top < innerHeight;
    visible ? activate(slot) : deactivate(slot);
  });
  const observer = new IntersectionObserver(refresh);
  slots.forEach(slot => observer.observe(slot.element));
  return {
    query: () => query,
    refresh,
    restore(hash) {
      query = hash.split('?')[1] || '';
      if (store) store.set(query ? selectionFromHash(hash) : {}, { replace: true, history: false });
    },
    destroy() { observer.disconnect(); slots.forEach(deactivate); },
  };
}

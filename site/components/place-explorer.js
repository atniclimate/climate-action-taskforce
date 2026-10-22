import { esc } from '../chapters/shared.js';
import { assetURL } from '../data/catalog.js';

let leafletPromise;
function leaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (!leafletPromise) leafletPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script'); script.src = new URL('../assets/vendor/leaflet-1.9.4/leaflet.js', import.meta.url);
    script.onload = () => resolve(window.L); script.onerror = () => { script.remove(); leafletPromise = null; reject(new Error('The map could not load. The place list still works.')); };
    document.head.append(script);
  });
  return leafletPromise;
}

export function mountPlaceExplorer(element, { catalog, store, loadAsset }) {
  element.classList.add('place-explorer');
  element.innerHTML = `<div class="place-presets" aria-label="Geographic stories">${catalog.cohorts.map(cohort => `<button type="button" data-story="${esc(cohort.id)}">${esc(cohort.label)}</button>`).join('')}</div><div class="place-layout"><div class="place-map-panel"><div class="place-map-actions"><button data-map-toggle>Interact with map</button><button data-extent>Reset extent</button><button data-list-toggle aria-expanded="false">Search / list</button></div><div class="place-map" data-map-keys tabindex="0" role="region" aria-label="Reference map. Use the place list for equivalent selection."></div><p class="place-map-caption">Reference geography, not live conditions or a jurisdictional determination. <span data-map-source></span></p></div><div class="place-sheet"><div class="place-search" hidden><label>Find a Nation or regional context<input type="search" data-search placeholder="Type a name"></label><label>Place<select data-place size="5"></select></label><p data-search-count class="caption"></p></div><div data-place-readout aria-live="polite"></div><label data-area-label>Climate source area<select data-area></select></label><label class="place-lens">Geographic lens<select data-lens>${catalog.lenses.map(item => `<option value="${esc(item.id)}">${esc(item.label)}</option>`).join('')}</select></label><a class="place-next" href="#scenarios/pathways">View pathways for this place →</a></div></div><p class="place-status" data-map-status role="status"></p>`;
  const mapNode = element.querySelector('.place-map'), readout = element.querySelector('[data-place-readout]');
  const placeSelect = element.querySelector('[data-place]'), areaSelect = element.querySelector('[data-area]');
  let map, layers, observer, controller, version = 0, disposed = false, gesture = false;
  const showList = () => { element.querySelector('.place-search').hidden = false; element.querySelector('[data-list-toggle]').setAttribute('aria-expanded', 'true'); };
  const list = () => {
    const query = element.querySelector('[data-search]').value.trim().toLocaleLowerCase();
    const places = catalog.places.filter(place => place.name.toLocaleLowerCase().includes(query));
    placeSelect.innerHTML = places.map(place => `<option value="${esc(place.id)}">${esc(place.name)}${place.kind === 'region' ? ' · regional context' : ''}</option>`).join('');
    placeSelect.value = store.get().selection.place;
    element.querySelector('[data-search-count]').textContent = `${places.length} matching places. All ${catalog.coverage.nations} Nation identities remain listed, including unavailable matches.`;
  };
  const choose = (id, areaId = '', story = '') => {
    const place = catalog.places.find(item => item.id === id);
    const selectedArea = areaId || (place?.area_ids.length === 1 ? place.area_ids[0] : '');
    const area = catalog.areas[selectedArea];
    store.set({ release: catalog.release_id, place: id, area: selectedArea, story, ...(area ? { family: area.family, baseline: area.baseline_id } : {}) });
  };
  const update = async ({ selection, primary, errors }) => {
    ++version; const current = version; controller?.abort(); controller = new AbortController();
    placeSelect.value = selection.place;
    element.querySelector('[data-lens]').value = selection.lens;
    areaSelect.innerHTML = `<option value="">${primary?.area_ids.length > 1 ? 'Choose one area; no automatic average' : 'No source area selected'}</option>${(primary?.area_ids || []).map(id => `<option value="${esc(id)}">${esc(catalog.areas[id]?.name || id)}</option>`).join('')}`;
    areaSelect.value = selection.area;
    element.querySelector('[data-area-label]').hidden = primary?.area_ids.length === 1;
    const area = catalog.areas[selection.area];
    readout.innerHTML = errors.length ? `<p class="notice">${errors.map(esc).join(' ')}</p>` : `<h2>${esc(primary.name)}</h2><p class="place-role">${esc(primary.kind === 'region' ? 'Regional context; not a Nation projection' : primary.mapping_status)}${primary.shared ? ' · shared climate source area' : ''}</p><p>${esc(primary.missing_reason || area?.geometry_role || 'Choose a source area to inspect its geographic support.')}</p>${area ? `<p class="caption">${esc(area.name)} · ${esc(catalog.families.find(item => item.id === area.family)?.label)}</p><p class="caption">${esc((area.memberships?.[selection.lens] || []).join(' · ') || 'No validated membership in this lens.')}</p>` : ''}`;
    if (primary?.proxy) readout.insertAdjacentHTML('beforeend', '<p class="notice">Borrowed climate-area proxy. These values do not resolve this Nation’s own geography.</p>');
    if (primary?.kind === 'reference') readout.querySelector('.place-role').textContent = 'Reference geography only; no Nation or climate association';
    if (primary?.mapping_caution) readout.insertAdjacentHTML('beforeend', `<details class="place-provenance"><summary>Source-area association</summary><p>${esc(primary.mapping_caution)}</p></details>`);
    element.querySelector('[data-map-status]').textContent = errors.length ? 'Choose a place from the list to use this release.' : '';
    if (!map || errors.length) return;
    layers.clearLayers();
    const cohort = catalog.cohorts.find(item => item.id === selection.story);
    const viewId = primary?.view || area?.view || cohort?.view || 'conus';
    const view = catalog.views[viewId];
    if (!view) return;
    try {
      const base = await loadAsset(catalog, view.geometry_file, { signal: controller.signal });
      if (disposed || current !== version) return;
      if (view.relief_file) window.L.imageOverlay(assetURL(catalog.files[view.relief_file].path), view.bounds, { opacity: .9, interactive: false }).addTo(layers);
      window.L.geoJSON(base, { style: feature => ({ color: feature.properties?.kind === 'river' ? '#356775' : '#727866', weight: feature.properties?.kind === 'river' ? 1 : .7, fillOpacity: 0, interactive: false }) }).addTo(layers);
      for (const fileId of [area?.lens_files?.[selection.lens], area?.geometry_file, view.reference_geometry_file].filter(Boolean)) {
        const shape = await loadAsset(catalog, fileId, { signal: controller.signal });
        if (disposed || current !== version) return;
        window.L.geoJSON(shape, { style: { color: fileId === area?.geometry_file ? '#155f65' : '#586f39', weight: fileId === area?.geometry_file ? 3 : 1.2, fillOpacity: .07 }, interactive: false }).addTo(layers);
      }
      if (cohort?.geometry_file) {
        const shape = await loadAsset(catalog, cohort.geometry_file, { signal: controller.signal });
        if (disposed || current !== version) return;
        window.L.geoJSON(shape, { style: { color: '#a84018', weight: 2.5, fillOpacity: .05 }, interactive: false }).addTo(layers);
      }
      const points = Object.values(catalog.areas).filter(item => item.view === viewId && item.point);
      points.forEach(point => {
        const matches = catalog.places.filter(item => item.area_ids.includes(point.id));
        const place = matches.find(item => item.id === selection.place) || (matches.length === 1 ? matches[0] : null);
        if (!matches.length) return;
        const selected = point.id === selection.area;
        window.L.circleMarker(point.point, { radius: selected ? 7 : 3.5, color: selected ? '#a84018' : '#155f65', weight: selected ? 3 : 1, fillOpacity: selected ? 1 : .55 }).addTo(layers).on('click', () => {
          if (place) choose(place.id, point.id);
          else {
            showList();
            element.querySelector('[data-search]').value = '';
            placeSelect.innerHTML = `<option value="">Choose an associated Nation</option>${matches.map(item => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('')}`;
            element.querySelector('[data-search-count]').textContent = `${matches.length} Nation identities share this source area. Choose the intended Nation; the marker does not establish shared sovereign territory.`;
            placeSelect.focus();
          }
        });
      });
      const bounds = cohort?.bounds || (area?.bounds && area.view !== 'alaska' ? area.bounds : view.bounds);
      map.fitBounds(bounds, { animate: false, padding: [20, 20], maxZoom: cohort ? 6 : 8 });
      element.querySelector('[data-map-source]').textContent = viewId === 'hawaii' ? 'Natural Earth · Native Resilience 2025 climate divisions. EPA/CEC 2010 does not cover Hawaii; no Nation or climate-series association is asserted.' : 'Natural Earth · EPA/CEC 2010 · USGS WBD 2025 · Native/Census 2025. Source areas are not complete Nation territories.';
      if (cohort) element.querySelector('[data-map-status]').textContent = `${cohort.tribe_ids.length} associated Nations · source-area climate, not a cohort average.`;
    } catch (error) { if (error.name !== 'AbortError' && current === version) { element.querySelector('[data-map-status]').textContent = `${error.message} The selected-place list remains available.`; showList(); } }
  };
  element.oninput = event => { if (event.target.matches('[data-search]')) list(); };
  element.onchange = event => {
    if (event.target === placeSelect) choose(placeSelect.value);
    if (event.target === areaSelect) choose(store.get().selection.place, areaSelect.value);
    if (event.target.matches('[data-lens]')) store.set({ lens: event.target.value });
  };
  element.onclick = event => {
    const story = event.target.closest('[data-story]');
    if (story) { const cohort = catalog.cohorts.find(item => item.id === story.dataset.story); choose(cohort.default_place, cohort.default_area, cohort.id); }
    if (event.target.closest('[data-list-toggle]')) { showList(); element.querySelector('[data-search]').focus(); }
    if (event.target.closest('[data-extent]')) update(store.get());
    if (event.target.closest('[data-map-retry]')) { mapNode.replaceChildren(); initializeMap(); }
    if (event.target.closest('[data-map-toggle]') && map) { gesture = !gesture; for (const name of ['dragging', 'touchZoom', 'scrollWheelZoom', 'doubleClickZoom']) map[name][gesture ? 'enable' : 'disable'](); event.target.textContent = gesture ? 'Return to page' : 'Interact with map'; if (gesture) mapNode.focus(); }
  };
  const unsubscribe = store.subscribe(update); list(); update(store.get());
  const initializeMap = () => leaflet().then(L => {
    if (disposed) return;
    map = L.map(mapNode, { dragging: false, touchZoom: false, scrollWheelZoom: false, doubleClickZoom: false, zoomAnimation: false, fadeAnimation: false, attributionControl: false, minZoom: 2, maxZoom: 9 });
    layers = L.layerGroup().addTo(map);
    observer = new ResizeObserver(() => map.invalidateSize({ pan: false, debounceMoveend: true })); observer.observe(mapNode); update(store.get());
  }).catch(error => { if (!disposed) {
    const selected = store.get(), area = catalog.areas[selected.selection.area];
    const view = catalog.views[selected.primary?.view || area?.view || 'conus'];
    mapNode.innerHTML = `<img class="place-fallback" src="${assetURL(catalog.files[view.relief_file].path)}" alt="Static regional relief context. Use the list for place selection; this image does not show the selected source-area outline."><button data-map-retry>Retry interactive map</button>`;
    element.querySelector('[data-map-status]').textContent = error.message; showList();
  } });
  initializeMap();
  return () => { disposed = true; ++version; controller?.abort(); unsubscribe(); observer?.disconnect(); map?.stop(); map?.remove(); element.oninput = null; element.onchange = null; element.onclick = null; };
}

const root = new URL('../', import.meta.url);
const cache = new Map();
let catalogPromise;

export function assetURL(path) {
  if (typeof path !== 'string' || !/^(?:data|assets)\/explorer\/[a-zA-Z0-9_./-]+$/.test(path) || path.split('/').includes('..')) throw new Error('Invalid explorer asset path.');
  return new URL(path, root);
}

export function loadCatalog() {
  if (!catalogPromise) catalogPromise = fetch(new URL('data/explorer/catalog.json', root), { signal: AbortSignal.timeout(15000) }).then(async response => {
    if (!response.ok) throw new Error('Place evidence could not load. Reconnect and try again.');
    const catalog = await response.json();
    if (!catalog.release_id || !catalog.default_selection || !Array.isArray(catalog.places) || !catalog.files) throw new Error('The place evidence catalog is incomplete.');
    for (const asset of Object.values(catalog.files)) assetURL(asset.path);
    return catalog;
  }).catch(error => { catalogPromise = null; throw error; });
  return catalogPromise;
}

export async function loadAsset(catalog, id, { signal } = {}) {
  const asset = catalog.files[id];
  if (!asset) throw new Error('This evidence is unavailable in this release.');
  const key = `${catalog.release_id}:${id}`;
  if (cache.has(key)) return cache.get(key);
  const response = await fetch(assetURL(asset.path), { signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error('This scene has not loaded. Reconnect and try again.');
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== asset.bytes) throw new Error('The evidence file is incomplete. Reload to try again.');
  const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(byte => byte.toString(16).padStart(2, '0')).join('');
  if (digest !== asset.sha256) throw new Error('The evidence file does not match this release. Reload to try again.');
  if (signal?.aborted) throw new DOMException('Selection changed', 'AbortError');
  const value = JSON.parse(new TextDecoder().decode(bytes));
  cache.set(key, value);
  return value;
}

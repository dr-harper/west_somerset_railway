// Operator settings, held in the browser.
//
// These are testing conveniences rather than configuration the public
// should see, so they live per-browser in localStorage instead of in
// Firestore: switching one on must not change what a visitor sees. Every
// read and write is guarded, because localStorage throws outright in some
// contexts (private windows, blocked site data) rather than returning
// empty.

const KEY = 'wsr.admin.settings';

export interface AdminSettings {
  /** Inject a synthetic running service, so the live views can be
   *  exercised on a closed day. */
  testTrain: boolean;
}

const DEFAULTS: AdminSettings = { testTrain: false };

type Listener = (settings: AdminSettings) => void;
const listeners = new Set<Listener>();

let cache: AdminSettings | null = null;

export function getSettings(): AdminSettings {
  if (cache) return cache;
  // Settled locally first: `cache` is module-level and other functions can
  // reassign it, so the compiler will not treat it as non-null after the
  // try/catch however obvious that is to read.
  let settings: AdminSettings;
  try {
    const raw = window.localStorage.getItem(KEY);
    settings = raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
  } catch {
    settings = { ...DEFAULTS };
  }
  cache = settings;
  return settings;
}

export function getSetting<K extends keyof AdminSettings>(
  key: K
): AdminSettings[K] {
  return getSettings()[key];
}

export function setSetting<K extends keyof AdminSettings>(
  key: K,
  value: AdminSettings[K]
): void {
  const next = { ...getSettings(), [key]: value };
  cache = next;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // A setting that cannot be persisted still applies to this session.
  }
  listeners.forEach(listener => listener(next));
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

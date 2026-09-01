import { useEffect, useState } from 'react';
import { getDownloadURL, ref } from 'firebase/storage';
import { storage } from '../firebase';

/**
 * Where detection stills and clips come from.
 *
 * Two different places, for a reason. On a laptop the files sit next to the
 * pipeline that wrote them and a Vite plugin serves them straight off disk,
 * which is the only way the annotator can be quick. Deployed, they live in a
 * private bucket and are fetched with the signed-in user's own token.
 *
 * The bucket is private on purpose. The *observations* — that something
 * passed Williton at 14:47 — are facts about the railway and are published
 * freely. The frames those observations were read from are Railcam's, and
 * rehosting them to the open web is not ours to do. So storage.rules gates
 * them on the operator grant, and this module reports refusal as a state to
 * render rather than letting it arrive as a broken image.
 *
 * Paths were once root-absolute `/captures/...`, which resolved only when
 * the app was served from a domain root. Under a base path every keyframe
 * 404'd while local dev looked perfect — the worst kind of bug in an
 * operator tool, because the page still renders and simply shows nothing.
 */

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

/** Where the pipeline's files sit inside the bucket. Matches storage.rules. */
const PREFIX = 'captures';

export type CaptureState =
  /** No file was recorded for this episode. */
  | 'none'
  /** Being fetched. */
  | 'loading'
  /** Have a URL. */
  | 'ready'
  /** There is a file, and this viewer may not have it. */
  | 'forbidden'
  /** There is a file and it could not be fetched. */
  | 'missing';

export interface Capture {
  url: string | null;
  state: CaptureState;
}

/**
 * The dev-server path. Exported because the annotator writes back to the
 * same files and needs to name them the same way.
 */
export function captureUrl(filename: string | null | undefined): string | null {
  if (!filename) return null;
  return `${BASE}/${PREFIX}/${filename}`;
}

/**
 * Resolved download URLs, kept for the life of the page.
 *
 * getDownloadURL is a round trip per object and the events list renders a
 * thumbnail per episode, so without this a scroll through a busy day costs
 * hundreds of requests for files it has already resolved once. In-flight
 * promises are shared too, so ten components asking for the same still at
 * the same moment make one request between them.
 */
const resolved = new Map<string, string>();
const inFlight = new Map<string, Promise<string>>();

function download(filename: string): Promise<string> {
  const already = inFlight.get(filename);
  if (already) return already;
  const request = getDownloadURL(ref(storage!, `${PREFIX}/${filename}`))
    .then(url => {
      resolved.set(filename, url);
      inFlight.delete(filename);
      return url;
    })
    .catch(error => {
      inFlight.delete(filename);
      throw error;
    });
  inFlight.set(filename, request);
  return request;
}

/** Whether files are served off the local disk rather than the bucket. */
export const servedLocally = import.meta.env.DEV;

/**
 * The answer that needs no network: nothing recorded, a local dev file, or
 * one already resolved. Returning null means it has to be fetched.
 */
function immediate(filename: string | null | undefined): Capture | null {
  if (!filename) return { url: null, state: 'none' };
  if (servedLocally) return { url: captureUrl(filename), state: 'ready' };
  const cached = resolved.get(filename);
  if (cached) return { url: cached, state: 'ready' };
  if (!storage) return { url: null, state: 'missing' };
  return null;
}

export function useCapture(filename: string | null | undefined): Capture {
  const known = immediate(filename);
  // Tagged with the file it describes, so a result arriving after the
  // component has moved on to another episode is not shown against it.
  const [fetched, setFetched] = useState<{ file: string; capture: Capture } | null>(null);

  useEffect(() => {
    if (known || !filename) return;
    let current = true;
    download(filename)
      .then(url => {
        if (current) setFetched({ file: filename, capture: { url, state: 'ready' } });
      })
      .catch((error: { code?: string }) => {
        if (!current) return;
        // Refusal and absence are different facts and the operator needs to
        // be told which. "You are not an operator yet" is something someone
        // can act on; "image failed to load" is not.
        const denied = error?.code === 'storage/unauthorized';
        setFetched({
          file: filename,
          capture: { url: null, state: denied ? 'forbidden' : 'missing' },
        });
      });
    return () => { current = false; };
  }, [filename, known]);

  if (known) return known;
  if (fetched && fetched.file === filename) return fetched.capture;
  return { url: null, state: 'loading' };
}

/** What to say instead of showing a frame that will not arrive. */
export function captureNote(state: CaptureState): string | null {
  switch (state) {
    case 'forbidden':
      return 'Footage is shown to operators only';
    case 'missing':
      return 'Still not available';
    case 'none':
      return 'No still recorded';
    default:
      return null;
  }
}

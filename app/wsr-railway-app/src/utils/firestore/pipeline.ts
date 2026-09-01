import { doc, getDoc } from 'firebase/firestore';
import { db } from '../../firebase';
import type { Pipeline } from '../../services/health';

/**
 * When the detection pipeline last pushed data here.
 *
 * The control room only ever sees what has been uploaded, and upload is a
 * separate step from capture. Without this the two failures are
 * indistinguishable: a watcher that has stopped and an upload that has not
 * run both look like a line where nothing is happening.
 */
export async function fetchPipeline(): Promise<Pipeline | null> {
  if (!db) return null;
  const snapshot = await getDoc(doc(db, 'status', 'pipeline'));
  if (!snapshot.exists()) return null;
  const data = snapshot.data() as Partial<Pipeline>;
  return data.uploaded_at
    ? { uploaded_at: data.uploaded_at, latest_episode: data.latest_episode ?? null }
    : null;
}

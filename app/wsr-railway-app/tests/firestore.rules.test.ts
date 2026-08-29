/**
 * Security rules for the episode verification queue.
 *
 * Run with the emulator on 8085:
 *   npx vitest run tests/firestore.rules.test.ts
 */
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment,
} from '@firebase/rules-unit-testing';
import { doc, getDoc, setDoc, updateDoc } from 'firebase/firestore';
import { readFileSync } from 'node:fs';
import { afterAll, beforeAll, beforeEach, describe, it } from 'vitest';

let env: RulesTestEnvironment;

const VERIFIER = 'verifier-uid';
const STRANGER = 'stranger-uid';
const EPISODE = 'episodes/20260829T080000_blue_anchor';

beforeAll(async () => {
  env = await initializeTestEnvironment({
    projectId: 'demo-wsr-rules',
    firestore: {
      host: '127.0.0.1',
      port: 8085,
      rules: readFileSync(new URL('../../../firestore.rules', import.meta.url), 'utf8'),
    },
  });
});

afterAll(async () => env?.cleanup());

beforeEach(async () => {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async context => {
    const db = context.firestore();
    await setDoc(doc(db, 'verifiers', VERIFIER), { email: 'michael@example.com' });
    await setDoc(doc(db, EPISODE), {
      camera: 'blue_anchor',
      peak_conf: 0.94,
      status: 'unverified',
      verification: null,
    });
  });
});

describe('episodes', () => {
  it('are readable by anyone', async () => {
    await assertSucceeds(getDoc(doc(env.unauthenticatedContext().firestore(), EPISODE)));
  });

  it('cannot be verified by an anonymous visitor', async () => {
    const db = env.unauthenticatedContext().firestore();
    await assertFails(updateDoc(doc(db, EPISODE), { status: 'confirmed' }));
  });

  it('cannot be verified by a signed-in stranger', async () => {
    const db = env.authenticatedContext(STRANGER).firestore();
    await assertFails(updateDoc(doc(db, EPISODE), { status: 'confirmed' }));
  });

  it('can be verified by an approved verifier', async () => {
    const db = env.authenticatedContext(VERIFIER).firestore();
    await assertSucceeds(updateDoc(doc(db, EPISODE), {
      status: 'confirmed',
      verification: { at: '2026-08-29T17:00:00', notes: 'the 08:10' },
    }));
  });

  it('protect detection data from a verifier', async () => {
    const db = env.authenticatedContext(VERIFIER).firestore();
    await assertFails(updateDoc(doc(db, EPISODE), { peak_conf: 0.99 }));
  });

  it('cannot be created or deleted from a client', async () => {
    const db = env.authenticatedContext(VERIFIER).firestore();
    await assertFails(setDoc(doc(db, 'episodes/invented'), { camera: 'nowhere' }));
  });
});

describe('verifiers', () => {
  it('cannot be self-granted', async () => {
    const db = env.authenticatedContext(STRANGER).firestore();
    await assertFails(setDoc(doc(db, 'verifiers', STRANGER), { email: 'x' }));
  });
});

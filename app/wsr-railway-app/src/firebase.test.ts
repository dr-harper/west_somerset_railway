import { describe, expect, it } from 'vitest';
import { emulatorHost } from './firebase';

/**
 * The host was pinned to an IP in .env.local, which is correct for one
 * network only. Changing Wi-Fi left the control room pointing at a machine
 * that no longer existed, and it showed an empty page rather than an error.
 */
describe('emulatorHost', () => {
  it('falls back to localhost where there is no page to ask', () => {
    expect(emulatorHost(':8085')).toEqual(['localhost', 8085]);
    expect(emulatorHost('8085')).toEqual(['localhost', 8085]);
  });

  it('honours a host written down explicitly', () => {
    expect(emulatorHost('localhost:8085')).toEqual(['localhost', 8085]);
    expect(emulatorHost('192.168.1.238:8085')).toEqual(['192.168.1.238', 8085]);
  });
});

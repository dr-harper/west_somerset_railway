import { copyFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import type { Plugin } from 'vite'

/**
 * A 404.html for static hosts, so routes other than "/" exist.
 *
 * The app routes in the browser, but GitHub Pages only serves files. Asking
 * for /live-trains looks for a file of that name, does not find one, and
 * returns 404 — so every page except the root was unreachable by link or by
 * refresh, and the episode links the control room hands out could not be
 * opened at all.
 *
 * Pages serves 404.html for anything it cannot match. Making that a copy of
 * index.html hands the URL to the router, which knows what to do with it.
 * Not a redirect: the address stays as typed, so the deep link still lands
 * where it was pointed.
 */
export function spaFallback(): Plugin {
  return {
    name: 'wsr-spa-fallback',
    apply: 'build',
    closeBundle() {
      const dir = resolve(__dirname, 'dist')
      const index = resolve(dir, 'index.html')
      if (!existsSync(index)) return
      copyFileSync(index, resolve(dir, '404.html'))
    },
  }
}

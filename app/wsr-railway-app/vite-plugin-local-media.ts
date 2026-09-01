import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Plugin } from 'vite'
import sirv from 'sirv'

/**
 * Serves the captures and reference frames while developing, and never in a
 * build.
 *
 * These used to be symlinks inside public/, which Vite copies wholesale into
 * the output: `dist` came to 2.7GB, against a GitHub Pages limit of 1GB. It
 * would either fail the deploy or publish every frame and clip the cameras
 * have ever recorded — footage that is not ours to republish.
 *
 * apply: 'serve' is the whole point. The operator tools need these files on
 * a laptop; a public build must not carry them.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOTS: Record<string, string> = {
  '/captures': resolve(HERE, '../../train_detection/captures'),
  '/reference': resolve(HERE, '../../train_detection/working_images'),
}

export function localMedia(): Plugin {
  return {
    name: 'wsr-local-media',
    apply: 'serve',
    configureServer(server) {
      for (const [route, dir] of Object.entries(ROOTS)) {
        if (!existsSync(dir)) {
          server.config.logger.warn(`[wsr] ${dir} is missing; ${route} will 404`)
          continue
        }
        server.middlewares.use(route, sirv(dir, { dev: true, etag: true }))
      }
    },
  }
}

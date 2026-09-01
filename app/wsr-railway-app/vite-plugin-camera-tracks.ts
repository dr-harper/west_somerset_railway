import { readFile, writeFile, copyFile, mkdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Plugin } from 'vite'

/**
 * Reading and writing the camera annotations, from inside the dev server.
 *
 * Tracing track is part of running the railway monitor, not a side tool, so
 * it belongs in the control room with everything else. The obstacle was
 * only ever that a browser cannot write a file: the annotator had its own
 * Python server on another port, which meant a second thing to start, a
 * second thing to notice had stopped, and a page in a different visual
 * language that the cameras screen could not even link to.
 *
 * Middleware here removes the second server rather than adding a third
 * component. The endpoint exists wherever the app is being served from, so
 * it follows the app onto whatever network the laptop is on.
 *
 * Writing is refused unless the file is where it is expected to be. This
 * edits the file the detection pipeline reads on its next run, and creating
 * a fresh empty one in the wrong directory would silently un-annotate every
 * camera on the line.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const TRACKS = resolve(HERE, '../../train_detection/camera_tracks.json')
const NOTE = 'Track centrelines in 854x480 image space, ordered from the Bishops '
  + 'Lydeard end towards Minehead. Traced in the control room.'

async function readBody(request: NodeJS.ReadableStream): Promise<string> {
  const chunks: Buffer[] = []
  for await (const chunk of request) chunks.push(chunk as Buffer)
  return Buffer.concat(chunks).toString('utf8')
}

export function cameraTracks(): Plugin {
  return {
    name: 'wsr-camera-tracks',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/api/camera-tracks', (request, response, next) => {
        void (async () => {
          try {
            if (!existsSync(TRACKS)) {
              response.statusCode = 500
              response.end(JSON.stringify({
                error: `camera_tracks.json not found at ${TRACKS}`,
              }))
              return
            }

            if (request.method === 'GET') {
              response.setHeader('Content-Type', 'application/json')
              response.setHeader('Cache-Control', 'no-store')
              response.end(await readFile(TRACKS, 'utf8'))
              return
            }

            if (request.method === 'PUT') {
              const payload = JSON.parse(await readBody(request))
              const cameras = Object.keys(payload).filter(k => !k.startsWith('_'))
              if (!cameras.length) {
                // An empty save is how a bad round-trip destroys a week of
                // tracing. It is refused rather than written.
                response.statusCode = 400
                response.end(JSON.stringify({
                  error: 'refusing to write annotations for no cameras',
                }))
                return
              }

              // Kept beside the file it replaces, so a bad edit is one copy
              // away from being undone.
              const backups = resolve(HERE, '../../train_detection/.track_backups')
              await mkdir(backups, { recursive: true })
              const stamp = new Date().toISOString().replace(/[:.]/g, '-')
              await copyFile(TRACKS, resolve(backups, `camera_tracks.${stamp}.json`))

              payload._note = NOTE
              await writeFile(TRACKS, JSON.stringify(payload, null, 1))
              response.setHeader('Content-Type', 'application/json')
              response.end(JSON.stringify({ saved: true, cameras: cameras.length }))
              return
            }

            next()
          } catch (error) {
            response.statusCode = 500
            response.end(JSON.stringify({ error: String(error) }))
          }
        })()
      })
    },
  }
}

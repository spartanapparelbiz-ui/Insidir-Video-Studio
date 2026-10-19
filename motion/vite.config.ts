import {defineConfig, type Plugin} from 'vite';
import motionCanvasModule from '@motion-canvas/vite-plugin';
import fs from 'node:fs';
import path from 'node:path';

// The vite plugin ships as CommonJS; unwrap the default export.
const motionCanvas = ((motionCanvasModule as any).default ?? motionCanvasModule) as typeof motionCanvasModule;

const FONTS = path.resolve(__dirname, '../insidir_studio/fonts');

// Serve the studio's bundled fonts at /studio-fonts/* (no copies in this folder).
function studioFonts(): Plugin {
  return {
    name: 'insidir:fonts',
    configureServer(server) {
      server.middlewares.use('/studio-fonts', (req, res, next) => {
        const name = path.basename(decodeURIComponent((req.url || '').split('?')[0]));
        const file = path.join(FONTS, name);
        if (!/\.(otf|ttf)$/.test(name) || !fs.existsSync(file)) return next();
        res.setHeader('Content-Type', name.endsWith('.ttf') ? 'font/ttf' : 'font/otf');
        fs.createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  // IVS_JOB_DIR holds data.json and the media for one render; the editor uses ./public.
  publicDir: process.env.IVS_JOB_DIR || 'public',
  plugins: [motionCanvas({project: './src/project.ts'}), studioFonts()],
  server: {fs: {allow: [path.resolve(__dirname), FONTS]}},
  logLevel: 'warn',
});

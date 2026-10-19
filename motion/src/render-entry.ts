// Headless render: load the job's data, then render the project through the pipe exporter.
import {Renderer, Vector2} from '@motion-canvas/core';
import type {RenderData} from './lib/data';

declare global {
  interface Window {
    ivsLog?: (msg: string) => void;
    ivsStart?: () => Promise<void>;
  }
}

async function main() {
  const data: RenderData = await (await fetch('/data.json', {cache: 'no-store'})).json();
  window.__IVS_DATA__ = data;
  await Promise.all([
    document.fonts.load('800 80px Inter'),
    document.fonts.load('700 80px Inter'),
    document.fonts.load('400 80px "Patrick Hand"'),
  ]);
  const project = (await import('./project?project')).default;
  project.logger.onLogged.subscribe((p: any) => window.ivsLog?.(`[${p.level}] ${p.message}${p.stack ? '\n' + p.stack : ''}`));
  const renderer = new Renderer(project);
  const settings = {
    ...project.meta.getFullRenderingSettings(),
    name: 'ivs',
    range: [0, data.total] as [number, number],
    fps: data.fps,
    size: new Vector2(data.width, data.height),
    resolutionScale: 1,
    background: data.palette.bg,
    exporter: {name: 'ivs-pipe', options: {}},
  };
  await renderer.render(settings as any);
}

window.ivsStart = main;

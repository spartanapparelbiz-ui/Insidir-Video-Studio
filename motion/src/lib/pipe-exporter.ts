// Sends every rendered frame to the Node render script (exposed by Playwright as
// window.ivsFrame), which pipes it into FFmpeg. Nothing is written by the browser.
import type {Exporter, ExporterClass, Plugin, Project, RendererResult, RendererSettings} from '@motion-canvas/core';
import {BoolMetaField, ObjectMetaField} from '@motion-canvas/core';

declare global {
  interface Window {
    ivsFrame?: (frame: number, dataUrl: string) => Promise<void>;
    ivsDone?: (result: number) => Promise<void>;
  }
}

class PipeExporter implements Exporter {
  public static readonly id = 'ivs-pipe';
  public static readonly displayName = 'Insidir Studio pipe';

  public static meta() {
    return new ObjectMetaField(this.displayName, {unused: new BoolMetaField('unused', false)});
  }

  public static async create(_project: Project, _settings: RendererSettings) {
    return new PipeExporter();
  }

  public async handleFrame(canvas: HTMLCanvasElement, frame: number) {
    if (!window.ivsFrame) throw new Error('ivsFrame bridge missing');
    await window.ivsFrame(frame, canvas.toDataURL('image/png'));
  }

  public async stop(result: RendererResult) {
    await window.ivsDone?.(result as unknown as number);
  }
}

export function pipeExporterPlugin(): Plugin {
  return {
    name: 'insidir:pipe-exporter',
    exporters(): ExporterClass[] {
      return [PipeExporter as unknown as ExporterClass];
    },
  };
}

// Production layer for the cinematic templates: lighting, film grain, vignette, a
// handheld camera with punch-ins and whip transitions, a progress bar and kinetic captions.
import {Img, Node, Rect, Txt, blur, type View2D} from '@motion-canvas/2d';
import {
  all,
  createRef,
  easeInCubic,
  easeInOutSine,
  easeOutBack,
  easeOutCubic,
  easeOutExpo,
  linear,
  loop,
  type Reference,
  spawn,
  type ThreadGenerator,
  waitFor,
} from '@motion-canvas/core';
import type {RenderData, Word} from './data';
import {until} from './timing';

export const W = 1080;
export const H = 1920;

function canvas(w: number, h: number, draw: (g: CanvasRenderingContext2D) => void): string {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  draw(c.getContext('2d')!);
  return c.toDataURL('image/png');
}

// deterministic noise so every render of a project looks the same
function rng(seed: number) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

export function backdrop(data: RenderData): string {
  return canvas(W, H, g => {
    const grad = g.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, '#15171a');
    grad.addColorStop(0.55, data.palette.bg);
    grad.addColorStop(1, '#050505');
    g.fillStyle = grad;
    g.fillRect(0, 0, W, H);
  });
}

function softLight(color: string, alpha: number, size = 900): string {
  return canvas(size, size, g => {
    const r = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    r.addColorStop(0, color.replace('A', String(alpha)));
    r.addColorStop(1, color.replace('A', '0'));
    g.fillStyle = r;
    g.fillRect(0, 0, size, size);
  });
}

function vignette(): string {
  return canvas(W, H, g => {
    const r = g.createRadialGradient(W / 2, H * 0.45, H * 0.25, W / 2, H * 0.45, H * 0.75);
    r.addColorStop(0, 'rgba(0,0,0,0)');
    r.addColorStop(1, 'rgba(0,0,0,0.72)');
    g.fillStyle = r;
    g.fillRect(0, 0, W, H);
  });
}

export interface Stage {
  caps: Reference<Node>;
  cam: Reference<Node>;
  content: Reference<Node>;
  flash: Reference<Rect>;
  overlay: Reference<Node>;
}

// Background lights + camera group + grain/vignette/progress on top.
export function stage(view: View2D, data: RenderData): Stage {
  const cam = createRef<Node>();
  const caps = createRef<Node>();
  const content = createRef<Node>();
  const flash = createRef<Rect>();
  const overlay = createRef<Node>();
  const lightA = createRef<Img>();
  const lightB = createRef<Img>();
  view.fill(data.palette.bg);
  view.add(<Img src={backdrop(data)} width={W} height={H} />);
  view.add(<Img ref={lightA} src={softLight('rgba(190,205,220,A)', 0.16)} width={1500} height={1500} x={-260} y={-520} />);
  view.add(<Img ref={lightB} src={softLight('rgba(233,228,218,A)', 0.09)} width={1300} height={1300} x={320} y={420} />);
  view.add(<Node ref={cam}><Node ref={content} /></Node>);
  view.add(<Node ref={caps} />);
  const progress = createRef<Rect>();
  view.add(
    <Node ref={overlay}>
      <Img src={vignette()} width={W} height={H} />
      <Rect ref={flash} width={W} height={H} fill="#ffffff" opacity={0} />
      <Rect width={W} height={8} y={-H / 2 + 4} fill="rgba(255,255,255,0.12)" />
      <Rect ref={progress} x={-W / 2} y={-H / 2 + 4} height={8} width={0} offset={[-1, 0]} fill="#ffffff" />
    </Node>,
  );
  spawn(progress().width(W, data.total, linear));
  // film grain is added by FFmpeg in the final pass (much faster than per-frame canvas noise)
  // slow drifting light and a handheld camera
  spawn(loop(Infinity, () => all(lightA().position([-180, -460], 4, easeInOutSine).to([-300, -560], 4, easeInOutSine))));
  spawn(loop(Infinity, () => all(lightB().position([260, 360], 5, easeInOutSine).to([360, 470], 5, easeInOutSine))));
  const rand = rng(99);
  spawn(loop(Infinity, () => cam().position([(rand() - 0.5) * 14, (rand() - 0.5) * 12], 1.4, easeInOutSine)));
  return {caps, cam, content, flash, overlay};
}

// Punch in on a cut, then a slow push for the rest of the beat.
export function* punch(s: Stage, seconds: number, strength = 1.1): ThreadGenerator {
  s.cam().scale(strength);
  yield* s.cam().scale(1, 0.45, easeOutExpo);
  yield* s.cam().scale(1.045, Math.max(0.2, seconds - 0.45), linear);
}

export function* whipOut(s: Stage): ThreadGenerator {
  s.cam().filters([blur(0)]);
  yield* all(s.content().x(-320, 0.13, easeInCubic), s.cam().filters.blur(26, 0.13));
}

export function* whipIn(s: Stage): ThreadGenerator {
  s.content().x(320);
  yield* all(s.content().x(0, 0.2, easeOutCubic), s.cam().filters.blur(0, 0.2));
}

export function* flashHit(s: Stage, amount = 0.32): ThreadGenerator {
  yield* s.flash().opacity(amount, 0.04).to(0, 0.22);
}

// ---------------------------------------------------------------- kinetic captions

function groups(words: Word[]): Word[][] {
  const out: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    if (cur.length) {
      const prev = cur[cur.length - 1];
      const chars = cur.reduce((n, x) => n + x.text.length + 1, 0) + w.text.length;
      if (cur.length >= 3 || chars > 16 || w.beat !== prev.beat || w.start - prev.end > 0.35 || /[.!?,;:]$/.test(prev.text)) {
        out.push(cur);
        cur = [];
      }
    }
    cur.push(w);
  }
  if (cur.length) out.push(cur);
  return out;
}

const clean = (t: string) => t.replace(/^["“]|["”,;:]+$/g, '').toUpperCase();

export function* kineticCaptions(layer: Node, data: RenderData, keywords: Set<string>, y = 420): ThreadGenerator {
  const end = data.end_card_start ?? data.total;
  const gs = groups(data.words);
  for (let gi = 0; gi < gs.length; gi++) {
    const g = gs[gi];
    if (g[0].start >= end) break;
    yield* until(Math.max(0, g[0].start - 0.04));
    const row = createRef<Rect>();
    const txts = g.map(() => createRef<Txt>());
    layer.add(
      <Rect ref={row} layout direction="row" gap={30} alignItems="center" y={y} scale={0.72} opacity={0} rotation={-2}>
        {g.map((w, i) => {
          const key = keywords.has(clean(w.text).replace(/[^A-Z0-9$%]/g, ''));
          return (
            <Txt
              ref={txts[i]}
              text={clean(w.text)}
              fontFamily="Inter"
              fontWeight={800}
              fontSize={key ? 112 : 100}
              letterSpacing={-2}
              fill="#8f8a82"
              stroke="#050505"
              lineWidth={9}
              strokeFirst
            />
          );
        })}
      </Rect>,
    );
    yield* all(row().scale(1, 0.2, easeOutBack), row().opacity(1, 0.08), row().rotation(0, 0.2, easeOutCubic));
    const next = gi + 1 < gs.length ? gs[gi + 1][0].start - 0.04 : end;
    const groupEnd = Math.min(next, g[g.length - 1].end + 0.5, end);
    for (let i = 0; i < g.length; i++) {
      yield* until(g[i].start);
      const t = txts[i]();
      t.fill('#ffffff');
      spawn(t.scale(1.06, 0.06).to(1, 0.12));
    }
    yield* until(groupEnd);
    const r = row();
    spawn(function* () {
      yield* all(r.opacity(0, 0.08), r.scale(0.92, 0.08));
      r.remove();
    });
  }
}

export {waitFor};

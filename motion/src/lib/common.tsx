import {Img, Node, Rect, Txt, Video, type View2D} from '@motion-canvas/2d';
import {all, createRef, easeOutCubic, type Reference, type ThreadGenerator, waitFor} from '@motion-canvas/core';
import type {AssetRef, Beat, RenderData} from './data';
import {figureIn, makeFigure, setPose, wave, type DotFigure} from './figure';
import {icon} from './icons';
import {R, Sketch, drawOn, eraseOff, type RoughStyle} from './rough';
import {until} from './timing';
import {F} from './fonts';

export const W = 1080;
export const H = 1920;
// Captions are burned in later by FFmpeg around y = +390 and the AI labels sit in the
// top-left corner, so templates keep their content between these lines.
export const SAFE_TOP = -800;
export const SAFE_BOTTOM = 300;

export function hand(data: RenderData, extra: RoughStyle = {}): RoughStyle {
  return {stroke: data.palette.ink, width: 6, roughness: 1.4, ...extra};
}

// Ink background with the Insidir halftone texture, denser towards the bottom corners.
export function halftone(data: RenderData): string {
  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const g = c.getContext('2d')!;
  g.fillStyle = data.palette.bg;
  g.fillRect(0, 0, W, H);
  g.fillStyle = data.palette.ink;
  const step = 30;
  for (let y = step / 2; y < H; y += step) {
    for (let x = step / 2; x < W; x += step) {
      const dx = Math.min(x, W - x) / (W / 2);
      const dy = (H - y) / H;
      const k = Math.max(0, 1 - Math.hypot(dx * 0.9, dy * 1.4));
      const r = 0.6 + k * 4.2;
      g.globalAlpha = 0.05 + k * 0.1;
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.fill();
    }
  }
  return c.toDataURL('image/png');
}

export function setup(view: View2D, data: RenderData) {
  view.fill(data.palette.bg);
  view.add(<Img src={halftone(data)} width={W} height={H} />);
}

export function wordsOf(data: RenderData, beat: Beat) {
  return data.words.filter(w => w.beat === beat.id);
}

// ------------------------------------------------------------------ headline

export function fitSize(text: string, big = 104, width = 920): number {
  const n = Math.max(1, text.length);
  const perLine = width / (big * 0.56);
  if (n <= perLine) return big;
  if (n <= perLine * 2) return Math.round(big * 0.86);
  return Math.round(big * 0.7);
}

export interface Headline {
  node: Node;
  txt: Reference<Txt>;
  line: Reference<Node>;
}

export function makeHeadline(data: RenderData, text: string, y: number, size?: number, width = 920): Headline {
  const txt = createRef<Txt>();
  const line = createRef<Node>();
  const fs = size ?? fitSize(text, 104, width);
  const node = (
    <Node y={y}>
      <Txt
        ref={txt}
        text=""
        fontFamily={F.head}
        fontWeight={800}
        fontSize={fs}
        lineHeight={fs * 1.08}
        letterSpacing={-1}
        fill={data.palette.ink}
        textAlign="center"
        width={width}
        textWrap
      />
      <Sketch ref={line} strokes={R.curve([[-220, 0], [0, 10], [220, -4]], hand(data, {stroke: data.palette.accent, width: 9, seed: text.length}))} />
    </Node>
  ) as Node;
  return {node, txt, line};
}

export function* writeHeadline(h: Headline, text: string, seconds = 0.6): ThreadGenerator {
  // measure the final layout first so the underline sits under the last line
  h.txt().text(text);
  h.line().y(h.txt().height() / 2 + 24);
  h.txt().text('');
  yield* h.txt().text(text, seconds);
  yield* drawOn(h.line(), 0.35);
}

// ------------------------------------------------------------------ doodle card

export function makeIconCard(data: RenderData, name: string, x: number, y: number, ring = 470, scale = 1.35): {ref: Reference<Node>; node: Node} {
  const ref = createRef<Node>();
  const strokes = [
    ...R.circle(0, 0, ring, hand(data, {stroke: data.palette.muted, width: 4, roughness: 2, seed: name.length + 3})),
    ...icon(name, hand(data, {width: 6 / scale}), data.palette.accent).map(s => ({
      ...s,
      d: scalePath(s.d, scale),
      width: s.width * scale,
    })),
  ];
  return {ref, node: (<Sketch ref={ref} strokes={strokes} x={x} y={y} />) as Node};
}

// Scale every number pair in an SVG path string (rough.js emits absolute M/C/L commands).
export function scalePath(d: string, k: number): string {
  return d.replace(/-?\d*\.?\d+(e-?\d+)?/g, n => String(Math.round(parseFloat(n) * k * 100) / 100));
}

// ------------------------------------------------------------------ screenshot in a sketched window

export function makeWindow(data: RenderData, asset: AssetRef, y: number, maxW = 960, maxH = 900) {
  const ref = createRef<Node>();
  const media = createRef<Img | Video>();
  const frame = createRef<Node>();
  const k = Math.min(maxW / asset.width, (maxH - 70) / asset.height);
  const w = Math.round(asset.width * k);
  const h = Math.round(asset.height * k);
  const top = -h / 2 - 60;
  const strokes = [
    ...R.rect(-w / 2 - 8, top, w + 16, h + 68, hand(data, {seed: 501, width: 5})),
    ...R.line(-w / 2 - 8, top + 52, w / 2 + 8, top + 52, hand(data, {seed: 502, width: 4})),
    ...[0, 1, 2].flatMap(i => R.circle(-w / 2 + 28 + i * 34, top + 26, 18, hand(data, {seed: 503 + i, width: 3}))),
  ];
  const node = (
    <Node ref={ref} y={y}>
      <Rect width={w} height={h} y={6} clip fill="#000">
        {asset.type === 'video' ? (
          <Video ref={media as any} src={asset.src} width={w} height={h} />
        ) : (
          <Img ref={media as any} src={asset.src} width={w} height={h} />
        )}
      </Rect>
      <Sketch ref={frame} strokes={strokes} />
    </Node>
  ) as Node;
  return {node, ref, media, frame, w, h};
}

// ------------------------------------------------------------------ figure helpers

export function addFigure(view: View2D, data: RenderData, x: number, y: number, unit = 11): DotFigure {
  const [node, fig] = makeFigure(data.palette.ink, unit, x, y);
  view.add(node);
  return fig;
}

export function* poseFor(fig: DotFigure, beat: Beat, fallback = 'explain'): ThreadGenerator {
  const p = beat.pose || fallback;
  yield* setPose(fig, p);
  if (p === 'wave') yield* wave(fig, 0.9);
}

// ------------------------------------------------------------------ end card

export function* endCard(view: View2D, data: RenderData, content: Node[], fig: DotFigure | null): ThreadGenerator {
  if (data.end_card_start === null) {
    yield* until(data.total);
    return;
  }
  yield* until(data.end_card_start);
  // The studio writes the wordmark, line and URL over this; leave the middle clear.
  yield* all(
    ...content.map(n => n.opacity(0, 0.3)),
    ...(fig ? [fig.root().position([0, -420], 0.45, easeOutCubic), fig.root().scale(0.9, 0.45)] : []),
  );
  if (fig) {
    yield* setPose(fig, 'cheer', 0.25);
    yield* wave(fig, 0.7);
  }
  yield* until(data.total);
}

export {all, figureIn, setPose, wave, waitFor, eraseOff, drawOn, until};

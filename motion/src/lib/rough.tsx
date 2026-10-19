// Rough.js drawings as Motion Canvas paths, so every hand-drawn stroke can be
// "drawn on" by animating the path's end from 0 to 1.
import {Node, Path} from '@motion-canvas/2d';
import {all, sequence, type ThreadGenerator} from '@motion-canvas/core';
import rough from 'roughjs';
import type {Options} from 'roughjs/bin/core';

const gen = rough.generator();

export interface Stroke {
  d: string;
  stroke: string;
  width: number;
  fill?: string;
}

export interface RoughStyle {
  stroke?: string;
  width?: number;
  fill?: string;
  fillStyle?: Options['fillStyle'];
  roughness?: number;
  bowing?: number;
  seed?: number;
  hachureGap?: number;
}

function opts(s: RoughStyle): Options {
  return {
    stroke: s.stroke ?? '#e9e4da',
    strokeWidth: s.width ?? 6,
    fill: s.fill,
    fillStyle: s.fillStyle ?? 'hachure',
    fillWeight: Math.max(2, (s.width ?? 6) * 0.5),
    hachureGap: s.hachureGap ?? 14,
    roughness: s.roughness ?? 1.3,
    bowing: s.bowing ?? 1.1,
    seed: s.seed ?? 7,
    preserveVertices: false,
  };
}

function toStrokes(drawable: ReturnType<typeof gen.line>): Stroke[] {
  const real = (c?: string) => (c && c !== 'none' && c !== 'transparent' ? c : undefined);
  return gen.toPaths(drawable).map(p => ({d: p.d, stroke: real(p.stroke) ?? '', width: real(p.stroke) ? p.strokeWidth : 0, fill: real(p.fill)}));
}

// Primitive builders (coordinates in pixels, centred wherever you like).
export const R = {
  line: (x1: number, y1: number, x2: number, y2: number, s: RoughStyle = {}) => toStrokes(gen.line(x1, y1, x2, y2, opts(s))),
  rect: (x: number, y: number, w: number, h: number, s: RoughStyle = {}) => toStrokes(gen.rectangle(x, y, w, h, opts(s))),
  circle: (x: number, y: number, d: number, s: RoughStyle = {}) => toStrokes(gen.circle(x, y, d, opts(s))),
  ellipse: (x: number, y: number, w: number, h: number, s: RoughStyle = {}) => toStrokes(gen.ellipse(x, y, w, h, opts(s))),
  poly: (pts: [number, number][], s: RoughStyle = {}) => toStrokes(gen.polygon(pts, opts(s))),
  lines: (pts: [number, number][], s: RoughStyle = {}) => toStrokes(gen.linearPath(pts, opts(s))),
  curve: (pts: [number, number][], s: RoughStyle = {}) => toStrokes(gen.curve(pts, opts(s))),
  arc: (x: number, y: number, w: number, h: number, a0: number, a1: number, s: RoughStyle = {}) =>
    toStrokes(gen.arc(x, y, w, h, a0, a1, false, opts(s))),
  path: (d: string, s: RoughStyle = {}) => toStrokes(gen.path(d, opts(s))),
};

// A hand-drawn arrow from (x1,y1) to (x2,y2) with a slight curve.
export function arrow(x1: number, y1: number, x2: number, y2: number, s: RoughStyle = {}): Stroke[] {
  const mx = (x1 + x2) / 2 + (y2 - y1) * 0.12;
  const my = (y1 + y2) / 2 - (x2 - x1) * 0.12;
  const ang = Math.atan2(y2 - my, x2 - mx);
  const head = 34;
  const a1: [number, number] = [x2 - head * Math.cos(ang - 0.5), y2 - head * Math.sin(ang - 0.5)];
  const a2: [number, number] = [x2 - head * Math.cos(ang + 0.5), y2 - head * Math.sin(ang + 0.5)];
  return [
    ...R.curve([[x1, y1], [mx, my], [x2, y2]], {...s, seed: (s.seed ?? 3) + 1}),
    ...R.lines([a1, [x2, y2], a2], {...s, seed: (s.seed ?? 3) + 2}),
  ];
}

// Hand-drawn scribble used to cross something out.
export function scribble(w: number, h: number, s: RoughStyle = {}): Stroke[] {
  const pts: [number, number][] = [];
  const n = 7;
  for (let i = 0; i <= n; i++) {
    pts.push([-w / 2 + (w * i) / n, i % 2 ? h / 2 : -h / 2]);
  }
  return [...R.lines(pts, s), ...R.line(-w / 2, -h / 2, w / 2, h / 2, {...s, seed: (s.seed ?? 1) + 9})];
}

// A Node holding the strokes as Path children (all starting undrawn).
export function Sketch(props: {strokes: Stroke[]; x?: number; y?: number; scale?: number; opacity?: number; drawn?: boolean; ref?: any}) {
  return (
    <Node x={props.x ?? 0} y={props.y ?? 0} scale={props.scale ?? 1} opacity={props.opacity ?? 1} ref={props.ref}>
      {props.strokes.map(st => (
        <Path
          data={st.d}
          stroke={st.stroke || null}
          lineWidth={st.width}
          fill={st.fill ?? null}
          lineCap="round"
          lineJoin="round"
          end={props.drawn ? 1 : 0}
        />
      ))}
    </Node>
  );
}

function paths(node: Node): Path[] {
  return node.findAll(n => n instanceof Path) as Path[];
}

// Draw the strokes on, one after another (overlapping), within `seconds`.
export function* drawOn(node: Node, seconds = 0.8): ThreadGenerator {
  const ps = paths(node);
  if (!ps.length) return;
  const each = Math.max(0.12, seconds * 0.6);
  const gap = ps.length > 1 ? (seconds - each) / (ps.length - 1) : 0;
  yield* sequence(Math.max(0, gap), ...ps.map(p => p.end(1, each)));
}

export function* eraseOff(node: Node, seconds = 0.3): ThreadGenerator {
  const ps = paths(node);
  yield* all(...ps.map(p => p.start(1, seconds)), node.opacity(0, seconds));
}

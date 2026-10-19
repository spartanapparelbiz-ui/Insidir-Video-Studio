// 6. Viral: kinetic captions, camera punch-ins, whip transitions, cinematic light and
// real Insidir screens in a floating device with a spotlight on what matters.
import {Circle, Img, Node, Rect, Txt, Video, type View2D} from '@motion-canvas/2d';
import {all, createRef, createSignal, easeOutBack, easeOutCubic, easeOutExpo, linear, sequence, spawn} from '@motion-canvas/core';
import type {Beat, RenderData} from '../lib/data';
import {figureIn, makeFigure, setPose, wave} from '../lib/figure';
import {icon} from '../lib/icons';
import {Sketch, drawOn} from '../lib/rough';
import {until} from '../lib/timing';
import {flashHit, kineticCaptions, punch, stage, whipIn, whipOut} from '../lib/cinema';
import {F} from '../lib/fonts';

export const norm = (t: string) => t.toUpperCase().replace(/[^A-Z0-9$%]/g, '');

export function headlineSize(text: string) {
  const n = text.length;
  return n <= 10 ? 176 : n <= 18 ? 148 : n <= 28 ? 122 : 100;
}

export function statement(text: string, y: number, size: number) {
  const words = text.split(/\s+/).filter(Boolean);
  const refs = words.map(() => createRef<Txt>());
  const node = (
    <Rect layout wrap="wrap" justifyContent="center" alignItems="center" gap={size * 0.22} rowGap={0} width={980} y={y}>
      {words.map((w, i) => (
        <Txt
          ref={refs[i]}
          text={w.toUpperCase()}
          fontFamily={F.head}
          fontWeight={800}
          fontSize={size}
          lineHeight={size * 1.02}
          letterSpacing={-size * 0.035}
          fill="#ffffff"
          opacity={0}
          scale={1.9}
        />
      ))}
    </Rect>
  ) as Rect;
  const show = () => sequence(0.07, ...refs.map(r => all(r().opacity(1, 0.06), r().scale(1, 0.22, easeOutExpo))));
  return {node, show};
}

export function eyebrow(text: string, y: number) {
  return (
    <Txt text={text.toUpperCase()} fontFamily={F.head} fontWeight={700} fontSize={46} letterSpacing={6} fill="#a9a59d" y={y} opacity={0} />
  ) as Txt;
}

export function cleanIcon(data: RenderData, name: string, y: number, scale = 1.3) {
  const strokes = icon(name || 'document', {stroke: '#ffffff', width: 7 / scale, roughness: 0.35, bowing: 0.2}, '#ffffff');
  return (<Sketch strokes={strokes} y={y} scale={scale} />) as Node;
}

export function number(b: Beat) {
  const m = b.emphasis.trim().match(/^([$€£]?)(\d+)(.*)$/);
  const prefix = m ? m[1] : '';
  const target = m ? parseInt(m[2], 10) : 0;
  const rest = (m ? m[3] : b.emphasis).trim();
  const v = createSignal(0);
  const big = (
    <Txt
      text={() => (m ? `${prefix}${Math.round(v())}` : b.emphasis.toUpperCase())}
      fontFamily={F.head}
      fontWeight={800}
      fontSize={m ? 400 : 150}
      letterSpacing={-12}
      fill="#ffffff"
      y={-300}
      scale={0.6}
      opacity={0}
      shadowColor="rgba(255,255,255,0.35)"
      shadowBlur={70}
    />
  ) as Txt;
  const label = (
    <Txt text={rest.toUpperCase()} fontFamily={F.head} fontWeight={800} fontSize={78} letterSpacing={-1} fill="#d9d5cd" y={-40} opacity={0} />
  ) as Txt;
  const show = () =>
    all(big.opacity(1, 0.1), big.scale(1, 0.5, easeOutBack), m ? v(target, 0.7, easeOutCubic) : v(0, 0), label.opacity(1, 0.4));
  return {nodes: [big, label], show};
}

export function device(b: Beat) {
  const a = b.asset!;
  const k = Math.min(900 / a.width, 960 / a.height);
  const w = Math.round(a.width * k);
  const h = Math.round(a.height * k);
  const [fx, fy] = b.focus;
  const px = (fx - 0.5) * w;
  const py = (fy - 0.5) * h;
  const media = createRef<Img | Video>();
  const shade = createRef<Node>();
  const ring = createRef<Circle>();
  const frame = createRef<Rect>();
  const mediaProps = {
    ref: media as any,
    src: a.src,
    width: w,
    height: h,
    offset: [(fx - 0.5) * 2, (fy - 0.5) * 2] as [number, number],
    x: px,
    y: py,
  };
  const node = (
    <Rect
      ref={frame}
      width={w}
      height={h}
      y={-150}
      radius={34}
      clip
      fill="#000"
      stroke="rgba(255,255,255,0.16)"
      lineWidth={3}
      shadowColor="rgba(0,0,0,0.85)"
      shadowBlur={90}
      shadowOffsetY={36}
      rotation={-5}
      scale={0.88}
      opacity={0}
    >
      {a.type === 'video' ? <Video {...mediaProps} /> : <Img {...mediaProps} />}
      <Node ref={shade} cache opacity={0}>
        <Rect width={w} height={h} fill="rgba(0,0,0,0.55)" />
        <Circle x={px} y={py} size={Math.min(420, w * 0.5)} fill="#ffffff" compositeOperation="destination-out" />
      </Node>
      <Circle ref={ring} x={px} y={py} size={Math.min(420, w * 0.5)} stroke="#ffffff" lineWidth={7} endAngle={-90} startAngle={-90} />
    </Rect>
  ) as Rect;
  const show = (dur: number) =>
    all(
      node.opacity(1, 0.2),
      node.scale(1, 0.5, easeOutExpo),
      node.rotation(-1.5, 0.6, easeOutCubic),
      (function* () {
        if (a.type === 'video') (media() as Video).play();
        yield* media().scale(1.22, Math.max(0.6, dur), linear);
      })(),
      (function* () {
        yield* until(b.start + Math.min(0.7, dur * 0.3));
        yield* all(shade().opacity(1, 0.3), ring().endAngle(270, 0.45, easeOutCubic));
      })(),
    );
  return {node, show};
}

export function* viral(view: View2D, data: RenderData) {
  const s = stage(view, data);
  const keywords = new Set<string>();
  for (const b of data.beats) {
    for (const w of `${b.headline} ${b.emphasis}`.split(/\s+/)) {
      const k = norm(w);
      if (k.length > 3 || /\d/.test(k)) keywords.add(k);
    }
  }
  spawn(kineticCaptions(s.caps(), data, keywords));

  let prev: Node[] = [];
  for (const [i, b] of data.beats.entries()) {
    const dur = b.end - b.start;
    if (i > 0) {
      yield* until(b.start - 0.13);
      yield* whipOut(s);
    }
    prev.forEach(n => n.remove());
    const items: Node[] = [];
    const reveals = [];
    if (b.asset) {
      const d = device(b);
      items.push(d.node);
      reveals.push(d.show(dur));
      if (b.headline) {
        const e = eyebrow(b.headline, -760);
        items.push(e);
        reveals.push(e.opacity(1, 0.3));
      }
    } else if (b.emphasis) {
      const n = number(b);
      items.push(...n.nodes);
      reveals.push(n.show());
      if (b.headline) {
        const e = eyebrow(b.headline, -640);
        items.push(e);
        reveals.push(e.opacity(1, 0.3));
      }
    } else {
      const text = b.headline || data.title;
      const size = headlineSize(text) * (i === 0 ? 1.08 : 1);
      const st = statement(text, -130, size);
      items.push(st.node);
      reveals.push(st.show());
      if (b.icon) {
        const ic = cleanIcon(data, b.icon, -620, 1.15);
        items.push(ic);
        reveals.push(drawOn(ic, 0.6));
      }
    }
    items.forEach(n => s.content().add(n));
    if (i > 0) spawn(whipIn(s));
    spawn(punch(s, dur, i === 0 || b.emphasis ? 1.16 : 1.08));
    if (i === 0 || b.emphasis) spawn(flashHit(s, i === 0 ? 0.4 : 0.25));
    yield* all(...reveals);
    prev = items;
  }

  // end card: the Insidir dot mark assembles; the studio writes the wordmark below it
  if (data.end_card_start !== null) {
    yield* until(data.end_card_start - 0.13);
    yield* whipOut(s);
    prev.forEach(n => n.remove());
    const [node, fig] = makeFigure('#e9e4da', 10, 0, -380);
    s.content().add(node);
    spawn(whipIn(s));
    spawn(flashHit(s, 0.16));
    yield* figureIn(fig, 0.5);
    yield* setPose(fig, 'cheer', 0.25);
    yield* wave(fig, 0.6);
  }
  yield* until(data.total);
}

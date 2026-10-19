// 7. Avatar host: a cartoon presenter talks to camera with real lip sync. Beats with footage
// or a figure go split-screen (content up top, the host pointing at it from below); talking
// beats cut to a close-up. Kinetic captions, punch-ins and whip transitions as in Viral.
import {Img, Node, type View2D} from '@motion-canvas/2d';
import {all, spawn} from '@motion-canvas/core';
import type {RenderData} from '../lib/data';
import {figureIn, makeFigure, setPose, wave} from '../lib/figure';
import {drawOn} from '../lib/rough';
import {until} from '../lib/timing';
import {flashHit, kineticCaptions, punch, stage, whipIn, whipOut} from '../lib/cinema';
import {blinkLoop, gesture, idle, makeMouth, makePresenter, nameTag} from '../lib/presenter';
import {cleanIcon, device, eyebrow, headlineSize, norm, number, statement} from './viral';

const CAPS_Y = -200;
const SPLIT = {x: 0, y: 560, scale: 0.92};
const CLOSE = {x: 0, y: 520, scale: 1.22};

function spotlight(): string {
  const c = document.createElement('canvas');
  c.width = c.height = 1000;
  const g = c.getContext('2d')!;
  const r = g.createRadialGradient(500, 500, 0, 500, 500, 500);
  r.addColorStop(0, 'rgba(233,228,218,0.20)');
  r.addColorStop(1, 'rgba(233,228,218,0)');
  g.fillStyle = r;
  g.fillRect(0, 0, 1000, 1000);
  return c.toDataURL('image/png');
}

function autoGesture(i: number, n: number, hasContent: boolean, pose: string): string {
  const map: Record<string, string> = {wave: 'wave', point: 'pointup', pointup: 'pointup', pointleft: 'pointleft', cheer: 'cheer',
    think: 'think', shrug: 'shrug', explain: 'explain', sad: 'shrug', walk: 'explain', stand: 'rest'};
  if (pose && map[pose]) return map[pose];
  if (i === 0) return 'wave';
  if (i === n - 1) return 'both';
  if (hasContent) return 'pointup';
  return ['explain', 'rest', 'think', 'explain'][i % 4];
}

export function* avatarHost(view: View2D, data: RenderData) {
  const s = stage(view, data);
  const keywords = new Set<string>();
  for (const b of data.beats) for (const w of `${b.headline} ${b.emphasis}`.split(/\s+/)) {
    const k = norm(w);
    if (k.length > 3 || /\d/.test(k)) keywords.add(k);
  }
  const end = data.end_card_start ?? data.total;
  // the host sits in front of a soft spotlight, inside the camera group so punch-ins move both
  const host = new Node({});
  s.cam().add(host);
  host.add(<Img src={spotlight()} width={1400} height={1400} y={480} />);
  const [pNode, p] = makePresenter(data.character || 'dot', CLOSE.x, CLOSE.y, CLOSE.scale);
  host.add(pNode);
  makeMouth(p, data.mouth ?? [], data.mouth_w ?? [], data.fps);
  spawn(blinkLoop(p, end));
  spawn(idle(p, end));
  spawn(kineticCaptions(s.caps(), data, keywords, CAPS_Y));
  const tag = nameTag(p, 1800 - 960);
  tag.opacity(0);
  host.add(tag);
  spawn(function* () {
    yield* tag.opacity(1, 0.3);
    yield* until(Math.min(3, end - 0.5));
    yield* tag.opacity(0, 0.3);
  });

  let prev: Node[] = [];
  const n = data.beats.length;
  for (const [i, b] of data.beats.entries()) {
    const dur = b.end - b.start;
    if (i > 0) {
      yield* until(b.start - 0.13);
      yield* whipOut(s);
    }
    prev.forEach(x => x.remove());
    const items: Node[] = [];
    const reveals = [];
    const hasContent = !!(b.asset || b.emphasis);
    if (b.asset) {
      const d = device(b);
      // fit the device (drawn up to 900x960 at y=-150) into the band above the captions
      const k = Math.min(900 / b.asset.width, 960 / b.asset.height);
      const sc = Math.min(0.96, 940 / (b.asset.width * k), 520 / (b.asset.height * k));
      const wrap = new Node({y: -515 + 150 * sc, scale: sc});
      wrap.add(d.node);
      items.push(wrap);
      reveals.push(d.show(dur));
      if (b.headline) {
        const e = eyebrow(b.headline, -810);
        items.push(e);
        reveals.push(e.opacity(1, 0.3));
      }
    } else if (b.emphasis) {
      const num = number(b);
      const wrap = new Node({y: -380, scale: 0.8});
      num.nodes.forEach(x => wrap.add(x));
      items.push(wrap);
      reveals.push(num.show());
      if (b.headline) {
        const e = eyebrow(b.headline, -810);
        items.push(e);
        reveals.push(e.opacity(1, 0.3));
      }
    } else {
      const text = b.headline || data.title;
      const st = statement(text, -620, Math.min(118, headlineSize(text) * 0.8));
      items.push(st.node);
      reveals.push(st.show());
      if (b.icon && i > 0) {
        const ic = cleanIcon(data, b.icon, -820, 0.8);
        items.push(ic);
        reveals.push(drawOn(ic, 0.6));
      }
    }
    items.forEach(x => s.content().add(x));
    if (i > 0) spawn(whipIn(s));
    spawn(punch(s, dur, i === 0 || b.emphasis ? 1.12 : 1.06));
    if (i === 0 || b.emphasis) spawn(flashHit(s, i === 0 ? 0.3 : 0.2));
    const shot = hasContent ? SPLIT : CLOSE;
    // cut (not glide) between framings, like a two-camera shoot
    p.root().position([shot.x, shot.y]);
    p.root().scale(shot.scale);
    spawn(gesture(p, autoGesture(i, n, hasContent, b.pose), 0.45));
    yield* all(...reveals);
    prev = items;
  }

  // end card: the host waves goodbye, then the Insidir dot mark assembles
  yield* until(end - 0.13);
  yield* whipOut(s);
  prev.forEach(x => x.remove());
  host.remove();
  if (data.end_card_start !== null) {
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


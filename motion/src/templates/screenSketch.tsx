// 5. Screen sketch: real Insidir screenshots or recordings in a hand-drawn window,
// circled where it matters, with the dot figure pointing at it.
import {Node, type View2D} from '@motion-canvas/2d';
import {spawn} from '@motion-canvas/core';
import type {RenderData} from '../lib/data';
import {setPose, talk} from '../lib/figure';
import {R, Sketch, arrow, drawOn} from '../lib/rough';
import {fadeRemove, nothing} from '../lib/fx';
import {addFigure, all, endCard, figureIn, hand, makeHeadline, makeIconCard, makeWindow, poseFor, setup, until, writeHeadline} from '../lib/common';

export function* screenSketch(view: View2D, data: RenderData) {
  setup(view, data);
  const FX = 400;
  const FY = 300;
  const unit = 6.5;
  const fig = addFigure(view, data, FX, FY, unit);
  spawn(talk(fig, data.words));
  let prev: Node[] = [];
  for (const [i, b] of data.beats.entries()) {
    yield* until(b.start);
    const hl = makeHeadline(data, b.headline, -730, 76);
    view.add(hl.node);
    const items: Node[] = [hl.node];
    let reveal;
    if (b.asset) {
      const win = makeWindow(data, b.asset, -200, 980, 860);
      view.add(win.node);
      win.media().opacity(0);
      items.push(win.node);
      const [fx, fy] = b.focus;
      const cx = (fx - 0.5) * win.w;
      const cy = (fy - 0.5) * win.h + 6 - 200;
      const ring = (<Sketch strokes={R.ellipse(cx, cy, Math.min(420, win.w * 0.45), Math.min(200, win.h * 0.3), hand(data, {stroke: data.palette.accent, width: 9, seed: 950 + i, roughness: 2.2}))} />) as Node;
      const hand0x = FX - 13 * unit;
      const hand0y = FY - 28 * unit;
      const pointer = (<Sketch strokes={arrow(hand0x - 20, hand0y - 10, cx + Math.min(210, win.w * 0.22) * Math.sign(hand0x - cx || 1), cy + 60, hand(data, {stroke: data.palette.accent, width: 7, seed: 970 + i}))} />) as Node;
      view.add(ring);
      view.add(pointer);
      items.push(ring, pointer);
      const media = win.media();
      if (b.asset.type === 'video') (media as any).play();
      const dur = Math.max(0.5, b.end - b.start);
      spawn(all(media.scale(1.12, dur), media.position([-(fx - 0.5) * win.w * 0.12, -(fy - 0.5) * win.h * 0.12], dur)));
      reveal = (function* () {
        yield* all(drawOn(win.frame(), 0.5), media.opacity(1, 0.4));
        yield* all(drawOn(ring, 0.5), drawOn(pointer, 0.45), setPose(fig, 'pointleft'));
      })();
    } else {
      const card = makeIconCard(data, b.icon || 'laptop', 0, -230, 520, 1.45);
      view.add(card.node);
      items.push(card.ref());
      reveal = all(drawOn(card.ref(), 0.9), poseFor(fig, b, 'explain'));
    }
    yield* all(
      fadeRemove(prev, 0.25),
      i === 0 ? figureIn(fig, 0.5) : nothing(),
      b.headline ? writeHeadline(hl, b.headline, 0.45) : nothing(),
      reveal,
    );
    prev = items;
  }
  yield* endCard(view, data, prev, fig);
}

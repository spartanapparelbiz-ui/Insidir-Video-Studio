// 4. Big number: an approved figure written huge and circled, with a doodle.
import {Node, Txt, type View2D} from '@motion-canvas/2d';
import {easeOutBack, spawn} from '@motion-canvas/core';
import type {RenderData} from '../lib/data';
import {talk} from '../lib/figure';
import {R, Sketch, drawOn} from '../lib/rough';
import {fadeRemove, nothing} from '../lib/fx';
import {addFigure, all, endCard, figureIn, hand, makeHeadline, makeIconCard, poseFor, setup, until, writeHeadline} from '../lib/common';

function split(e: string): [string, string] {
  const m = e.trim().match(/^([$€£]?\d[\d,.]*%?)\s*(.*)$/);
  return m ? [m[1], m[2]] : [e.trim(), ''];
}

export function* bigNumber(view: View2D, data: RenderData) {
  setup(view, data);
  const fig = addFigure(view, data, -340, 280, 9);
  spawn(talk(fig, data.words));
  let prev: Node[] = [];
  for (const [i, b] of data.beats.entries()) {
    yield* until(b.start);
    const hl = makeHeadline(data, b.headline, -690, 84);
    view.add(hl.node);
    const items: Node[] = [hl.node];
    let reveal;
    if (b.emphasis) {
      const [big, rest] = split(b.emphasis);
      const size = big.length > 3 ? 300 : 400;
      const num = (<Txt text={big} fontFamily="Inter" fontWeight={800} fontSize={size} fill={data.palette.ink} y={-330} scale={0.5} opacity={0} />) as Txt;
      const ring = (<Sketch strokes={R.ellipse(0, 0, Math.max(420, big.length * size * 0.62 + 140), size * 1.15, hand(data, {stroke: data.palette.accent, width: 10, seed: 900 + i, roughness: 2}))} y={-330} />) as Node;
      const sub = (<Txt text={rest} fontFamily="Patrick Hand" fontSize={96} fill={data.palette.ink} y={-40} opacity={0} />) as Txt;
      view.add(ring);
      view.add(num);
      view.add(sub);
      items.push(num, ring, sub);
      reveal = all(num.scale(1, 0.5, easeOutBack), num.opacity(1, 0.2), drawOn(ring, 0.7), sub.opacity(1, 0.6));
    } else {
      const card = makeIconCard(data, b.icon || 'document', 0, -250, 520, 1.45);
      view.add(card.node);
      items.push(card.ref());
      reveal = drawOn(card.ref(), 0.9);
    }
    yield* all(
      fadeRemove(prev, 0.25),
      i === 0 ? figureIn(fig, 0.5) : nothing(),
      poseFor(fig, b, b.emphasis ? 'pointup' : 'explain'),
      b.headline ? writeHeadline(hl, b.headline, 0.5) : nothing(),
      reveal,
    );
    prev = items;
  }
  yield* endCard(view, data, prev, fig);
}

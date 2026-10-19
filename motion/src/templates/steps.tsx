// 3. Step by step: numbered hand-drawn boxes joined by arrows, ticked off as you go.
import {Node, Txt, type View2D} from '@motion-canvas/2d';
import {easeInOutCubic, spawn} from '@motion-canvas/core';
import type {RenderData} from '../lib/data';
import {setPose, talk} from '../lib/figure';
import {icon} from '../lib/icons';
import {R, Sketch, arrow, drawOn} from '../lib/rough';
import {fadeRemove, nothing} from '../lib/fx';
import {addFigure, all, endCard, figureIn, hand, makeHeadline, setup, until, writeHeadline} from '../lib/common';
import {F} from '../lib/fonts';

const BOX_W = 780;
const BOX_H = 170;
const GAP = 235;
const X = -60;
const TOP = -590;

export function* steps(view: View2D, data: RenderData) {
  setup(view, data);
  const fig = addFigure(view, data, 0, 240, 11);
  spawn(talk(fig, data.words));
  const group = (<Node />) as Node;
  view.add(group);
  const boxes: Node[] = [];
  let intro: Node | null = null;
  for (const [i, b] of data.beats.entries()) {
    yield* until(b.start);
    if (i === 0) {
      const hl = makeHeadline(data, b.headline || data.title, -420, 118);
      view.add(hl.node);
      intro = hl.node;
      yield* all(figureIn(fig, 0.6), writeHeadline(hl, b.headline || data.title, 0.7), setPose(fig, b.pose || 'wave'));
      continue;
    }
    const n = boxes.length;
    const y = TOP + n * GAP;
    const text = b.headline || b.text;
    const box = (
      <Node y={y} x={X}>
        <Sketch strokes={R.rect(-BOX_W / 2, -BOX_H / 2, BOX_W, BOX_H, hand(data, {seed: 800 + i}))} />
        <Sketch strokes={R.circle(-BOX_W / 2 + 85, 0, 104, hand(data, {stroke: data.palette.accent, seed: 820 + i}))} />
        <Txt text={String(n + 1)} fontFamily={F.hand} fontSize={84} fill={data.palette.accent} x={-BOX_W / 2 + 85} y={4} opacity={0} />
        <Txt
          text={text}
          fontFamily={F.head}
          fontWeight={800}
          fontSize={text.length > 22 ? 46 : 58}
          lineHeight={text.length > 22 ? 52 : 64}
          fill={data.palette.ink}
          width={BOX_W - 210}
          textWrap
          x={70}
          opacity={0}
        />
      </Node>
    ) as Node;
    group.add(box);
    const link = n > 0 ? ((<Sketch strokes={arrow(X - 260, y - GAP + BOX_H / 2 + 6, X - 250, y - BOX_H / 2 - 8, hand(data, {seed: 840 + i, width: 5}))} />) as Node) : null;
    if (link) group.add(link);
    const tick = n > 0 ? ((<Sketch strokes={icon('check', hand(data, {width: 6}), data.palette.up)} x={X + BOX_W / 2 - 70} y={TOP + (n - 1) * GAP} scale={0.55} />) as Node) : null;
    if (tick) group.add(tick);
    const shift = Math.max(0, n - 3) * -GAP;
    const [sk1, sk2, num, label] = box.children() as Node[];
    yield* all(
      intro ? fadeRemove([intro], 0.3) : nothing(),
      n === 0 ? fig.root().position([430, 300], 0.5, easeInOutCubic) : nothing(),
      n === 0 ? fig.root().scale(0.55, 0.5) : nothing(),
      group.y(shift, 0.45, easeInOutCubic),
      drawOn(sk1, 0.6),
      drawOn(sk2, 0.4),
      num.opacity(1, 0.4),
      label.opacity(1, 0.5),
      link ? drawOn(link, 0.4) : nothing(),
      tick ? drawOn(tick, 0.4) : nothing(),
      setPose(fig, i === data.beats.length - 1 ? 'cheer' : b.pose || 'pointleft'),
    );
    intro = null;
    boxes.push(box);
  }
  // tick the last box too
  if (boxes.length) {
    const last = boxes.length - 1;
    const tick = (<Sketch strokes={icon('check', hand(data, {width: 6}), data.palette.up)} x={X + BOX_W / 2 - 70} y={TOP + last * GAP} scale={0.55} />) as Node;
    group.add(tick);
    yield* drawOn(tick, 0.4);
  }
  yield* endCard(view, data, [group, ...(intro ? [intro] : [])], fig);
}

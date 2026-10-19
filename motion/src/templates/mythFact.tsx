// 2. Myth vs fact: a card per beat; myths get scribbled out, facts get a check.
import {Node, Rect, Txt, type View2D} from '@motion-canvas/2d';
import {easeInCubic, easeOutCubic, spawn} from '@motion-canvas/core';
import type {RenderData} from '../lib/data';
import {setPose, talk} from '../lib/figure';
import {icon} from '../lib/icons';
import {R, Sketch, drawOn, scribble} from '../lib/rough';
import {nothing} from '../lib/fx';
import {addFigure, all, endCard, figureIn, fitSize, hand, setup, until, waitFor} from '../lib/common';

export function* mythFact(view: View2D, data: RenderData) {
  setup(view, data);
  const fig = addFigure(view, data, 380, 340, 8);
  spawn(talk(fig, data.words));
  let prev: Node | null = null;
  for (const [i, b] of data.beats.entries()) {
    yield* until(b.start);
    const label = (b.label || '').toUpperCase();
    const text = b.headline || b.text;
    const card = (
      <Node y={-290} x={1200}>
        <Rect width={872} height={552} fill={data.palette.bg} />
        <Sketch strokes={R.rect(-440, -280, 880, 560, hand(data, {seed: 600 + i}))} drawn />
        <Txt
          text={text}
          fontFamily="Inter"
          fontWeight={800}
          fontSize={fitSize(text, 96, 760)}
          lineHeight={fitSize(text, 96, 760) * 1.1}
          fill={data.palette.ink}
          width={760}
          textWrap
          textAlign="center"
          y={20}
        />
      </Node>
    ) as Node;
    if (label) {
      const color = label === 'MYTH' ? data.palette.down : label === 'FACT' ? data.palette.up : data.palette.accent;
      card.add(
        <Node x={-290} y={-285} rotation={-6}>
          <Rect width={label.length * 44 + 70} height={96} fill={data.palette.bg} />
          <Sketch strokes={R.rect(-(label.length * 22 + 35), -48, label.length * 44 + 70, 96, hand(data, {stroke: color, seed: 640 + i}))} drawn />
          <Txt text={label} fontFamily="Patrick Hand" fontSize={76} fill={color} />
        </Node>,
      );
    }
    view.add(card);
    // whip: the old card leaves first, the new one lands just behind it
    yield* all(
      prev ? prev.x(-1200, 0.3, easeInCubic) : nothing(),
      (function* () {
        if (prev) yield* waitFor(0.12);
        yield* card.x(0, 0.4, easeOutCubic);
      })(),
      i === 0 ? figureIn(fig, 0.5) : nothing(),
      setPose(fig, label === 'MYTH' ? 'think' : b.pose || 'pointleft'),
    );
    prev?.remove();
    prev = card;
    yield* waitFor(Math.min(0.9, Math.max(0.2, (b.end - b.start) * 0.35)));
    if (label === 'MYTH') {
      const mark = (<Sketch strokes={scribble(700, 250, hand(data, {stroke: data.palette.down, width: 12, seed: 700 + i}))} y={20} />) as Node;
      card.add(mark);
      yield* all(drawOn(mark, 0.6), setPose(fig, 'shrug'));
    } else if (label === 'FACT') {
      const mark = (<Sketch strokes={icon('check', hand(data, {width: 8}), data.palette.up)} x={330} y={190} scale={0.8} />) as Node;
      card.add(mark);
      yield* all(drawOn(mark, 0.5), setPose(fig, 'cheer'));
    }
  }
  yield* endCard(view, data, prev ? [prev] : [], fig);
}

// 1. Dot explainer: the Insidir dot figure explains, a doodle is drawn for each beat.
import {Node, Txt, type View2D} from '@motion-canvas/2d';
import {spawn} from '@motion-canvas/core';
import type {RenderData} from '../lib/data';
import {talk} from '../lib/figure';
import {nothing, fadeRemove} from '../lib/fx';
import {addFigure, all, drawOn, endCard, figureIn, makeHeadline, makeIconCard, makeWindow, poseFor, setup, until, writeHeadline} from '../lib/common';
import {F} from '../lib/fonts';

export function* dotExplainer(view: View2D, data: RenderData) {
  setup(view, data);
  const fig = addFigure(view, data, -300, 270, 10);
  spawn(talk(fig, data.words));
  let prev: Node[] = [];
  for (const [i, b] of data.beats.entries()) {
    yield* until(b.start);
    const hl = makeHeadline(data, b.headline, -650);
    view.add(hl.node);
    let visual: Node;
    let reveal;
    if (b.asset) {
      const win = makeWindow(data, b.asset, -200, 720, 640);
      win.node.x(150);
      view.add(win.node);
      win.media().opacity(0);
      visual = win.node;
      reveal = all(drawOn(win.frame(), 0.6), win.media().opacity(1, 0.5));
    } else {
      const card = makeIconCard(data, b.icon || 'document', 170, -170, 440, 1.25);
      view.add(card.node);
      visual = card.ref();
      reveal = drawOn(visual, 0.9);
    }
    const emph = b.emphasis
      ? ((<Txt text={b.emphasis} fontFamily={F.hand} fontSize={78} fill={data.palette.accent} x={170} y={130} opacity={0} />) as Node)
      : null;
    if (emph) view.add(emph);
    yield* all(
      fadeRemove(prev, 0.25),
      i === 0 ? figureIn(fig, 0.6) : nothing(),
      poseFor(fig, b, i === 0 ? 'wave' : 'explain'),
      b.headline ? writeHeadline(hl, b.headline, 0.5) : nothing(),
      reveal,
      emph ? emph.opacity(1, 0.5) : nothing(),
    );
    prev = [hl.node, visual, emph].filter(Boolean) as Node[];
  }
  yield* endCard(view, data, prev, fig);
}

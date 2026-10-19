import {makeScene2D} from '@motion-canvas/2d';
import {getData} from '../lib/data';
import {dotExplainer} from '../templates/dotExplainer';
import {mythFact} from '../templates/mythFact';
import {steps} from '../templates/steps';
import {bigNumber} from '../templates/bigNumber';
import {screenSketch} from '../templates/screenSketch';

export const TEMPLATES = {
  'dot-explainer': dotExplainer,
  'myth-fact': mythFact,
  steps,
  'big-number': bigNumber,
  'screen-sketch': screenSketch,
};

export default makeScene2D(function* (view) {
  const data = getData();
  const run = (TEMPLATES as any)[data.template] ?? dotExplainer;
  yield* run(view, data);
});

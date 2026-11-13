import {makeScene2D} from '@motion-canvas/2d';
import {getData} from '../lib/data';
import {frame} from '../lib/frame';
import {dotExplainer} from '../templates/dotExplainer';
import {mythFact} from '../templates/mythFact';
import {steps} from '../templates/steps';
import {bigNumber} from '../templates/bigNumber';
import {screenSketch} from '../templates/screenSketch';
import {viral} from '../templates/viral';
import {avatarHost} from '../templates/avatarHost';
import {chat} from '../templates/chat';
import {editorialStory} from '../templates/editorialStory';

export const TEMPLATES = {
  'dot-explainer': dotExplainer,
  'myth-fact': mythFact,
  steps,
  'big-number': bigNumber,
  'screen-sketch': screenSketch,
  viral,
  'avatar-host': avatarHost,
  chat,
  'editorial-story': editorialStory,
};

export default makeScene2D(function* (view) {
  const data = getData();
  // fit the 1080x1920 design into the chosen frame (1 for 9:16)
  view.scale(frame().scale);
  const run = (TEMPLATES as any)[data.template] ?? dotExplainer;
  yield* run(view, data);
});

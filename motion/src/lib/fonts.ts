// The project's chosen fonts. The studio declares two browser font aliases before rendering
// ("IVS Caption" and "IVS Head", one @font-face per weight pointing at the closest real file),
// so templates keep asking for weights 600-900 and never get a faux-bold font.
import {getData} from './data';

export const F = {
  // captions and spoken text (kinetic captions, chat bubbles)
  get cap(): string {
    return getData().fonts?.caption ? 'IVS Caption' : 'Inter';
  },
  // headlines, numbers, titles
  get head(): string {
    return getData().fonts?.head ? 'IVS Head' : 'Inter';
  },
  // the hand-drawn face of the sketch templates, unless a headline font was chosen
  get hand(): string {
    return getData().fonts?.head ? 'IVS Head' : 'Patrick Hand';
  },
};

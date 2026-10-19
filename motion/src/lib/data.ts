// The render contract between the Python studio and the Motion Canvas templates.

export interface AssetRef {
  src: string; // URL under the job folder, e.g. /media/a1.png
  type: 'image' | 'video';
  width: number;
  height: number;
  genuine?: boolean;
}

export interface Beat {
  id: string;
  start: number; // on-screen start (s)
  end: number; // on-screen end (s)
  speech_start: number;
  text: string;
  headline: string;
  icon: string;
  pose: string;
  label: string; // template-specific tag, e.g. MYTH / FACT
  emphasis: string; // approved figure to show big, e.g. "2 business days"
  asset: AssetRef | null;
  focus: [number, number];
}

export interface Word {
  text: string;
  start: number;
  end: number;
  beat: string;
}

export interface Palette {
  bg: string;
  ink: string;
  accent: string;
  up: string;
  down: string;
  muted: string;
}

export interface RenderData {
  template: string;
  width: number;
  height: number;
  fps: number;
  total: number;
  end_card_start: number | null;
  title: string;
  palette: Palette;
  beats: Beat[];
  words: Word[];
}

declare global {
  interface Window {
    __IVS_DATA__?: RenderData;
  }
}

export const SAMPLE: RenderData = {
  template: 'dot-explainer',
  width: 1080,
  height: 1920,
  fps: 30,
  total: 12,
  end_card_start: 10,
  title: 'Sample',
  palette: {bg: '#0c0c0b', ink: '#e9e4da', accent: '#ffd84d', up: '#2f996a', down: '#f94144', muted: '#77736c'},
  beats: [
    {id: 'b1', start: 0, end: 3.4, speech_start: 0.1, text: 'Ever wonder what executives do with their own stock?', headline: 'Insiders file too', icon: 'eye', pose: 'wave', label: '', emphasis: '', asset: null, focus: [0.5, 0.5]},
    {id: 'b2', start: 3.4, end: 6.8, speech_start: 3.5, text: 'They report trades on a Form 4 within two business days.', headline: 'Form 4', icon: 'calendar', pose: 'point', label: 'FACT', emphasis: '2 business days', asset: null, focus: [0.5, 0.5]},
    {id: 'b3', start: 6.8, end: 10, speech_start: 6.9, text: 'Insidir puts every filing in one place.', headline: 'One place', icon: 'document', pose: 'cheer', label: '', emphasis: '', asset: null, focus: [0.5, 0.5]},
  ],
  words: [],
};

export function getData(): RenderData {
  return (typeof window !== 'undefined' && window.__IVS_DATA__) || SAMPLE;
}

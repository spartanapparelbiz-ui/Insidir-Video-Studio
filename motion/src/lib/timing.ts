import {useTime, waitFor, type ThreadGenerator} from '@motion-canvas/core';

// Wait until an absolute time on the timeline (seconds). Keeps every template frame-exact
// with the narration, however long the beat animations take.
export function* until(t: number): ThreadGenerator {
  const now = useTime();
  if (t - now > 1e-4) yield* waitFor(t - now);
}

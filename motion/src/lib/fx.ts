import type {Node} from '@motion-canvas/2d';
import {all, type ThreadGenerator} from '@motion-canvas/core';

// Fade nodes out and drop them from the scene so later beats stay cheap to render.
export function* fadeRemove(nodes: (Node | null | undefined)[], seconds = 0.25): ThreadGenerator {
  const live = nodes.filter((n): n is Node => !!n);
  if (!live.length) return;
  yield* all(...live.map(n => n.opacity(0, seconds)));
  live.forEach(n => n.remove());
}

export function* nothing(): ThreadGenerator {}

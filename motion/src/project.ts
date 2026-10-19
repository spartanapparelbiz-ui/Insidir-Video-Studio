import {makeProject} from '@motion-canvas/core';
import main from './scenes/main?scene';
import {pipeExporterPlugin} from './lib/pipe-exporter';
import '@fontsource/patrick-hand/400.css';

export default makeProject({
  scenes: [main],
  plugins: [pipeExporterPlugin()],
});

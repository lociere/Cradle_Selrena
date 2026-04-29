import { defineExtension } from '@cradle-selrena/plugin-sdk';
import { VTubeStudioVesselPlugin } from './src/vtube-studio-vessel-plugin';

export default defineExtension({
  manifest: {
    activationEvents: ['onStartup'],
    contributes: {
      commands: [
        {
          command: 'vessel-vtube-studio.status',
          title: 'VTube Studio Vessel Status',
          category: 'VTube Studio',
        },
      ],
    },
  },
  plugin: new VTubeStudioVesselPlugin(),
});

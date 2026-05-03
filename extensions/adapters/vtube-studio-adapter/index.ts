import { defineExtension } from '@cradle-selrena/extension-sdk';
import { VTubeStudioAdapterExtension } from './src/vtube-studio-adapter-extension';

export default defineExtension({
  manifest: {
    activationEvents: ['onStartup'],
    contributes: {
      commands: [
        {
          command: 'vtube-studio-adapter.status',
          title: 'VTube Studio Adapter Status',
          category: 'VTube Studio',
        },
      ],
    },
  },
  extension: new VTubeStudioAdapterExtension(),
});


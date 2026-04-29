import { BasePlugin } from '@cradle-selrena/plugin-sdk';
import { VTubeStudioPluginConfig, VTubeStudioPluginConfigSchema } from '../config/schema';

export class VTubeStudioVesselPlugin extends BasePlugin<VTubeStudioPluginConfig> {
  constructor() {
    super(VTubeStudioPluginConfigSchema);
  }

  protected override async activate(): Promise<void> {
    this.logger.info('[vessel-vtube-studio] placeholder vessel activated', {
      transport: this.config.transport,
      enabled: this.config.features.enabled,
    });

    this.registerCommand(
      'vessel-vtube-studio.status',
      async () => ({
        enabled: this.config.features.enabled,
        transport: this.config.transport,
      }),
      {
        title: 'VTube Studio Vessel Status',
        category: 'VTube Studio',
      },
    );
  }

  protected override async deactivate(): Promise<void> {
    this.logger.info('[vessel-vtube-studio] placeholder vessel stopped');
  }
}
import type { ChannelReplyPayload } from '@cradle-selrena/protocol';
import { BaseExtension } from '@cradle-selrena/extension-sdk';
import { MyExtensionConfig, MyExtensionConfigSchema } from '../config/schema';

export class MyExtension extends BaseExtension<MyExtensionConfig> {
  constructor() {
    super(MyExtensionConfigSchema);
  }

  protected override async activate(): Promise<void> {
    this.logger.info('[my-extension] started', {
      features: this.config.features,
    });

    this.subscribe('action.channel.reply', (payload) => {
      this.handleReply(payload as ChannelReplyPayload);
    });

    this.registerCommand(
      'my-extension.ping',
      async () => {
        this.logger.info('[my-extension] ping command executed');
        return 'pong';
      },
      {
        title: 'Ping My Extension',
        category: 'My Extension',
      },
    );
  }

  protected override async deactivate(): Promise<void> {
    this.logger.info('[my-extension] stopped');
  }

  private handleReply(payload: ChannelReplyPayload): void {
    this.logger.debug('[my-extension] received AI reply', {
      traceId: payload.traceId,
    });
  }
}
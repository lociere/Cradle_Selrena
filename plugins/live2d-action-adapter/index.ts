import path from 'path';
import fs from 'fs';

import { BasePlugin } from '@cradle-selrena/plugin-sdk';

class Live2dActionAdapterPlugin extends BasePlugin {
  private _outputPath = '';

  protected override async activate(): Promise<void> {
    const outputDir = path.resolve(process.cwd(), 'runtime', 'live2d');
    await fs.promises.mkdir(outputDir, { recursive: true });
    this._outputPath = path.join(outputDir, 'action-stream.jsonl');

    this.logger.info('Live2D Action Adapter activated');

    this.subscribe('ActionStreamStartedEvent', (p) => { void this._append('ActionStreamStartedEvent', p); });
    this.subscribe('ActionStreamChunkEvent', (p) => { void this._append('ActionStreamChunkEvent', p); });
    this.subscribe('ActionStreamCompletedEvent', (p) => { void this._append('ActionStreamCompletedEvent', p); });
    this.subscribe('ActionStreamCancelledEvent', (p) => { void this._append('ActionStreamCancelledEvent', p); });
  }

  protected override async deactivate(): Promise<void> {
    this.logger.info('Live2D Action Adapter deactivated');
  }

  private async _append(eventType: string, payload: unknown): Promise<void> {
    const line = JSON.stringify({
      event_type: eventType,
      occurred_at: Date.now(),
      payload,
    });
    await fs.promises.appendFile(this._outputPath, line + '\n');
  }
}

export default new Live2dActionAdapterPlugin();

/**
 * 鎻掍欢鍏ュ彛 鈥?index.ts
 *
 * 銆愬繀椤诲瓨鍦ㄣ€戝鍑烘彃浠跺畾涔夈€?
 * ExtensionManager 鍚屾椂鍏煎锛?
 *   1. 鐩存帴瀵煎嚭鎻掍欢瀹炰緥
 *   2. 浣跨敤 defineExtension() 瀵煎嚭甯﹁ˉ鍏呭厓鏁版嵁鐨勫畾涔夊璞?
 *
 * 瑙勮寖锛?
 *   - 姝ゆ枃浠跺彧鍋氫竴浠朵簨锛氬疄渚嬪寲骞跺鍑烘彃浠剁被/瀹氫箟
 *   - 涓嶈鍦ㄦ鏂囦欢閲屽啓浠讳綍涓氬姟閫昏緫
 */
import { defineExtension } from '@cradle-selrena/extension-sdk';
import { MyExtension } from './src/my-extension';

export default defineExtension({
  manifest: {
    activationEvents: ['onStartup'],
    contributes: {
      commands: [
        {
          command: 'my-extension.ping',
          title: 'Ping My Extension',
          category: 'My Extension',
        },
      ],
    },
  },
  extension: new MyExtension(),
});


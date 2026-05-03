// 杩欎釜鏂囦欢鏄ず渚嬶紝鍙互鐩存帴鍒犻櫎銆?
// src/ 涓嬬殑浠ｇ爜缁撴瀯鐢变綘鑷畾銆?

/**
 * 銆愬彲閫夈€戝綋鍑虹珯鎿嶄綔杈冧负澶嶆潅鏃讹紝寤鸿鎻愬彇鍒版鐩綍銆?
 * 濡傛灉鎻掍欢閫昏緫绠€鍗曪紝鍙洿鎺ュ唴鑱斿湪涓绘彃浠剁被涓鐞嗭紝鏃犻渶姝ょ洰褰曘€?
 *
 * 鈹€鈹€ 璁捐鍘熷垯 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
 *
 * - Handler 閫氳繃鏋勯€犲嚱鏁板弬鏁版帴鍙椾緷璧栵紙logger銆乻ender 绛夛級锛屼笉鐩存帴
 *   import 鎻掍欢 SDK锛岄伩鍏嶅紩鍏ュ惊鐜緷璧栥€?
 * - Handler 鍙礋璐ｆ墽琛屽嚭绔欐搷浣滐紝涓嶅垽鏂槸鍚﹀簲璇ユ墽琛岋紙閭ｆ槸涓绘彃浠剁被鐨勮亴璐ｏ級銆?
 * - Handler 鍙鍗曞厓娴嬭瘯锛屼笉瑕佸湪姝ゅ紩鍏ュ鑷存祴璇曡祫婧愬姞杞藉鏉傜殑鍏朵粬渚濊禆銆?
 */

import type { IExtensionLogger } from '@cradle-selrena/protocol';
import type { ChannelReplyPayload } from '@cradle-selrena/protocol';

/** 鍙戦€佹秷鎭殑鍑芥暟绫诲瀷 */
type SendFn = (text: string) => Promise<boolean>;

export class ReplyHandler {
  constructor(
    private readonly _logger: IExtensionLogger,
    private readonly _send: SendFn,
  ) {}

  async handle(payload: ChannelReplyPayload): Promise<void> {
    this._logger.debug('[handler] 鏀跺埌 AI Core 鍥炲', { traceId: payload.traceId });

    const sent = await this._send(payload.text);
    if (!sent) {
      this._logger.warn('[handler] 鍙戦€佸け璐ワ紝瀹㈡埛绔湭灏辩华', {
        traceId: payload.traceId,
      });
    }
  }
}


import { SceneRoutingManager } from "../capabilities/scene/scene-routing-manager";
import { ExtensionSceneTranscriptService } from "../capabilities/scene/extension-scene-transcript-service";
import { AudioService } from "../capabilities/audio/audio-service";
import { ChannelRuntimeManager } from "../channel/ChannelRuntimeManager";
import { getLogger } from "../../foundation/logger/logger";
import {
  SceneRoutingRequest,
  SceneRoutingResult,
  ExtensionSceneTranscriptEntry,
  TTSSynthesizeRequest,
  TTSSynthesizeResponse,
  ASRRecognizeRequest,
  ASRRecognizeResponse,
  PerceptionMessageRequest,
  ChannelReplyEvent,
  PerceptionEvent,
  createTraceContext,
} from "@cradle-selrena/protocol";
import { AttentionSessionManager } from "../../domain/attention/attention-session-manager";
import { EventBus } from "../../foundation/event-bus/event-bus";
import { IngressGateManager } from "../../foundation/ingress-gate/ingress-gate-manager";

const logger = getLogger("perception-gateway");

export class PerceptionAppService {
  constructor(
    private sceneRoutingMgr: SceneRoutingManager,
    private transcriptService: ExtensionSceneTranscriptService,
    private audioService: AudioService,
    private channelRuntimeMgr: ChannelRuntimeManager,
    private attentionMgr: AttentionSessionManager) {}

  public async processIngress(event: PerceptionEvent): Promise<void> {
    // 鈹€鈹€ 鍏ョ珯闃叉姢锛堥€熺巼闄愬埗 路 鐔旀柇 路 灏辩华瀹堝崼锛夆攢鈹€
    const gate = IngressGateManager.instance;
    const gateResult = gate.admit(event.source);
    if (!gateResult.admitted) {
      logger.debug('感知输入被入站防护拒绝', {
        trace_id: event.id,
        source: event.source,
        rejection: gateResult.rejection?.type,
      });
      return;
    }

    const contentText = String(event.content?.text || '');
    const modality = event.content?.modality ?? ['text'];
    const familiarity = event.familiarity ?? 0;
    const addressMode = event.address_mode ?? 'direct';
    const items = event.content?.items ?? undefined;

    // 鈹€鈹€ 缁熶竴鎰熺煡鍏ュ彛鏃ュ織锛堟墍鏈夊閮ㄨ緭鍏ョ殑鍞竴鍙闂級鈹€鈹€
    logger.info('感知输入', {
      trace_id: event.id,
      source: event.source,
      sensory_type: event.sensoryType,
      modality,
      familiarity,
      content_preview: contentText.slice(0, 100) || '[非文本]',
    });

    const request: PerceptionMessageRequest = {
      id: event.id,
      sensoryType: event.sensoryType,
      source: event.source,
      timestamp: event.timestamp,
      familiarity,
      address_mode: addressMode,
      content: {
        text: contentText || undefined,
        modality,
        items: items as PerceptionMessageRequest['content']['items'],
      },
    };
    try {
      const channelRuntime = await this.channelRuntimeMgr.handleInboundMessage(request);
      logger.debug('通道运行态刷新完成', {
        source: channelRuntime.source,
        message_count: channelRuntime.messageCount,
        last_trace_id: channelRuntime.lastTraceId,
      });

      // 閫氳繃 AttentionSessionManager 娉ㄥ叆锛屽惎鐢ㄩ槻鎶栥€佹壒澶勭悊涓庣敓鎴愪腑鏂満鍒?
      const response = await this.attentionMgr.ingest(request);
      gate.complete(true);
      if (!response) {
        // 姝ゆ秷鎭鎵归噺鍚堝苟鎴栬涓柇锛屽洖澶嶅皢鐢辨壒娆′腑鏈€鍚庝竴鏉℃秷鎭礋璐ｅ彂甯?
        return;
      }
      // 娌夐粯闂細鏈堣閫夋嫨涓嶅紑鍙ｆ椂 reply_content 涓虹┖涓诧紝璺宠繃鍥炲浜嬩欢锛屾儏缁?璁板繂宸茬収甯稿鐞?
      if (!response.reply_content?.trim()) {
        logger.info('鏈堣閫夋嫨娌夐粯', { trace_id: event.id, scene_id: event.source });
        return;
      }
      // 灏嗗洖澶嶇粨鏋滃彂甯冨埌鍏ㄥ眬浜嬩欢鎬荤嚎锛屼緵瀵瑰簲閫傞厤鍣ㄦ崟鑾峰苟鍥炰紶
      await EventBus.instance.publish(
        new ChannelReplyEvent(
          { traceId: event.id, text: response.reply_content, emotionState: response.emotion_state },
          createTraceContext({ trace_id: event.id }),
        )
      );
    } catch (e) {
      gate.complete(false);
      logger.error('鎰熺煡澶勭悊澶辫触', {
        trace_id: event.id,
        source: event.source,
        error: e instanceof Error ? e.message : String(e),
        stack: e instanceof Error ? e.stack : undefined,
      });
    }
  }

  public async resolveScene(request: SceneRoutingRequest): Promise<SceneRoutingResult> {
    return this.sceneRoutingMgr.resolve(request);
  }

  public async appendSceneTranscript(extensionId: string, entry: ExtensionSceneTranscriptEntry): Promise<void> {
    return this.transcriptService.append(extensionId, entry);
  }

  public async synthesizeSpeech(request: TTSSynthesizeRequest): Promise<TTSSynthesizeResponse> {
    return this.audioService.synthesizeSpeech(request);
  }

  public async recognizeSpeech(request: ASRRecognizeRequest): Promise<ASRRecognizeResponse> {
    return this.audioService.recognizeSpeech(request);
  }
}


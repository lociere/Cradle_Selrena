import { SceneRoutingManager } from "../capabilities/scene/scene-routing-manager";
import { PluginSceneTranscriptService } from "../capabilities/scene/plugin-scene-transcript-service";
import { AudioService } from "../capabilities/audio/audio-service";
import { ChannelRuntimeManager } from "../channel/ChannelRuntimeManager";
import { getLogger } from "../../foundation/logger/logger";
import {
  SceneRoutingRequest,
  SceneRoutingResult,
  PluginSceneTranscriptEntry,
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
    private transcriptService: PluginSceneTranscriptService,
    private audioService: AudioService,
    private channelRuntimeMgr: ChannelRuntimeManager,
    private attentionMgr: AttentionSessionManager) {}

  public async processIngress(event: PerceptionEvent): Promise<void> {
    // ── 入站防护（速率限制 · 熔断 · 就绪守卫）──
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

    // ── 统一感知入口日志（所有外部输入的唯一可见门）──
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
      // 通过 AttentionSessionManager 注入，启用防抖、批处理与生成中断机制
      const response = await this.attentionMgr.ingest(request);
      gate.complete(true);
      if (!response) {
        // 此消息被批量合并或被中断，回复将由批次中最后一条消息负责发布
        return;
      }
      // 沉默门：月见选择不开口时 reply_content 为空串，跳过回复事件，情绪/记忆已照常处理
      if (!response.reply_content?.trim()) {
        logger.info('月见选择沉默', { trace_id: event.id, scene_id: event.source });
        return;
      }
      // 将回复结果发布到全局事件总线，供对应适配器捕获并回传
      await EventBus.instance.publish(
        new ChannelReplyEvent(
          { traceId: event.id, text: response.reply_content, emotionState: response.emotion_state },
          createTraceContext({ trace_id: event.id }),
        )
      );
    } catch (e) {
      gate.complete(false);
      logger.error('感知处理失败', {
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

  public async appendSceneTranscript(pluginId: string, entry: PluginSceneTranscriptEntry): Promise<void> {
    return this.transcriptService.append(pluginId, entry);
  }

  public async synthesizeSpeech(request: TTSSynthesizeRequest): Promise<TTSSynthesizeResponse> {
    return this.audioService.synthesizeSpeech(request);
  }

  public async recognizeSpeech(request: ASRRecognizeRequest): Promise<ASRRecognizeResponse> {
    return this.audioService.recognizeSpeech(request);
  }
}

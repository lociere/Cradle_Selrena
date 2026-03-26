import { SceneRoutingManager } from "../capabilities/scene/scene-routing-manager";
import { PluginSceneTranscriptService } from "../capabilities/scene/plugin-scene-transcript-service";
import { AudioService } from "../capabilities/audio/audio-service";
import { ChannelRuntimeManager } from "../channel/ChannelRuntimeManager";
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

export class PerceptionAppService {
  constructor(
    private sceneRoutingMgr: SceneRoutingManager,
    private transcriptService: PluginSceneTranscriptService,
    private audioService: AudioService,
    private channelRuntimeMgr: ChannelRuntimeManager,
    private attentionMgr: AttentionSessionManager) {}

  public async processIngress(event: PerceptionEvent): Promise<void> {
    const request: PerceptionMessageRequest = {
      id: event.id,
      sensoryType: event.sensoryType,
      source: event.source,
      timestamp: event.timestamp,
      content: event.content as PerceptionMessageRequest["content"],
    };
    try {
      // 通过 AttentionSessionManager 注入，启用防抖、批处理与生成中断机制
      const response = await this.attentionMgr.ingest(request);
      if (!response) {
        // 此消息被批量合并或被中断，回复将由批次中最后一条消息负责发布
        return;
      }
      // 将回复结果发布到全局事件总线，供对应适配器捕获并回传
      const { EventBus } = await import("../../foundation/event-bus/event-bus");
      await EventBus.instance.publish(
        new ChannelReplyEvent(
          { traceId: event.id, text: response.reply_content, emotionState: response.emotion_state },
          createTraceContext({ trace_id: event.id }),
        )
      );
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e);
      console.error("AI 感知处理失败", errMsg);
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

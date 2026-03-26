import path from "path";
import { promises as fs } from "fs";
import {
  ASRRecognizeRequest,
  ASRRecognizeResponse,
  TTSSynthesizeRequest,
  TTSSynthesizeResponse,
} from "@cradle-selrena/protocol";
import { getLogger } from "../../../foundation/logger/logger";
import { resolveRepoRoot } from "../../../foundation/utils/path-utils";

const logger = getLogger("audio-service");

export class AudioService {
  private static _instance: AudioService | null = null;

  public static get instance(): AudioService {
    if (!AudioService._instance) {
      AudioService._instance = new AudioService();
    }
    return AudioService._instance;
  }

  private constructor() {}

  public async synthesizeSpeech(request: TTSSynthesizeRequest): Promise<TTSSynthesizeResponse> {
    const text = (request.text || "").trim();
    if (!text) {
      return { status: "error", message: "text is required" };
    }

    try {
      const outputPath = await this.resolveOutputPath(request.output_path);
      await fs.mkdir(path.dirname(outputPath), { recursive: true });

      // 先落可播放的静音 wav 占位文件，确保链路可运行；后续可替换为真实 native TTS。
      const wavBuffer = this.createSilentWav(320);
      await fs.writeFile(outputPath, wavBuffer);

      logger.info("TTS 合成完成（占位实现）", { output_path: outputPath, text_length: text.length });
      return { status: "success", output_path: outputPath };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error("TTS 合成失败", { error: message });
      return { status: "error", message };
    }
  }

  public async recognizeSpeech(request: ASRRecognizeRequest): Promise<ASRRecognizeResponse> {
    const inputPath = (request.audio_path || "").trim();
    if (!inputPath) {
      return { status: "error", message: "audio_path is required" };
    }

    try {
      if (/^https?:\/\//i.test(inputPath)) {
        return { status: "success", text: "[语音消息]" };
      }

      const resolvedPath = path.isAbsolute(inputPath)
        ? inputPath
        : path.resolve(resolveRepoRoot(), inputPath);
      await fs.access(resolvedPath);

      const filename = path.basename(resolvedPath);
      logger.info("ASR 识别完成（占位实现）", { audio_path: resolvedPath });
      return { status: "success", text: `[语音转写占位] ${filename}` };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error("ASR 识别失败", { audio_path: inputPath, error: message });
      return { status: "error", message };
    }
  }

  private async resolveOutputPath(rawPath?: string): Promise<string> {
    if (rawPath && rawPath.trim()) {
      return path.isAbsolute(rawPath)
        ? rawPath
        : path.resolve(resolveRepoRoot(), rawPath);
    }

    const dir = path.resolve(resolveRepoRoot(), "runtime", "tts");
    const filename = `tts-${Date.now()}.wav`;
    return path.join(dir, filename);
  }

  private createSilentWav(durationMs: number): Buffer {
    const sampleRate = 16000;
    const channels = 1;
    const bitsPerSample = 16;
    const bytesPerSample = bitsPerSample / 8;
    const sampleCount = Math.max(1, Math.floor((sampleRate * durationMs) / 1000));
    const dataSize = sampleCount * channels * bytesPerSample;
    const buffer = Buffer.alloc(44 + dataSize);

    buffer.write("RIFF", 0);
    buffer.writeUInt32LE(36 + dataSize, 4);
    buffer.write("WAVE", 8);
    buffer.write("fmt ", 12);
    buffer.writeUInt32LE(16, 16);
    buffer.writeUInt16LE(1, 20);
    buffer.writeUInt16LE(channels, 22);
    buffer.writeUInt32LE(sampleRate, 24);
    buffer.writeUInt32LE(sampleRate * channels * bytesPerSample, 28);
    buffer.writeUInt16LE(channels * bytesPerSample, 32);
    buffer.writeUInt16LE(bitsPerSample, 34);
    buffer.write("data", 36);
    buffer.writeUInt32LE(dataSize, 40);

    return buffer;
  }
}
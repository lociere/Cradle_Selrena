import { execFile } from 'node:child_process';
import process from 'node:process';
import { promisify } from 'node:util';
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
const execFileAsync = promisify(execFile);

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

      let provider = 'fallback-wav';
      try {
        const systemProvider = await this.trySynthesizeWithSystemVoice(text, outputPath);
        if (systemProvider) {
          provider = systemProvider;
        } else {
          await fs.writeFile(outputPath, this.createFallbackWav(320));
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        logger.warn('系统 TTS 不可用，已切换为回退音频', { error: message, output_path: outputPath });
        await fs.writeFile(outputPath, this.createFallbackWav(320));
      }

      logger.info('TTS 合成完成', {
        output_path: outputPath,
        text_length: text.length,
        provider,
      });
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
      const fallbackText = path.parse(filename).name || filename;
      logger.warn('ASR 引擎未接入，返回文件名回退结果', {
        audio_path: resolvedPath,
        fallback_text: fallbackText,
      });
      return {
        status: 'success',
        text: fallbackText,
        message: 'ASR engine unavailable, returned filename fallback',
      };
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

  private async trySynthesizeWithSystemVoice(text: string, outputPath: string): Promise<string | null> {
    if (process.platform !== 'win32') {
      return null;
    }

    const script = [
      "$ErrorActionPreference = 'Stop'",
      'Add-Type -AssemblyName System.Speech',
      "$text = [Environment]::GetEnvironmentVariable('SELRENA_TTS_TEXT')",
      "$outputPath = [Environment]::GetEnvironmentVariable('SELRENA_TTS_OUTPUT')",
      "if ([string]::IsNullOrWhiteSpace($text)) { throw 'SELRENA_TTS_TEXT is empty' }",
      "if ([string]::IsNullOrWhiteSpace($outputPath)) { throw 'SELRENA_TTS_OUTPUT is empty' }",
      '$directory = Split-Path -Parent $outputPath',
      'if ($directory) { [System.IO.Directory]::CreateDirectory($directory) | Out-Null }',
      '$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer',
      'try {',
      '  $synth.SetOutputToWaveFile($outputPath)',
      '  $synth.Speak($text)',
      '} finally {',
      '  $synth.Dispose()',
      '}',
    ].join('; ');
    const encodedCommand = Buffer.from(script, 'utf16le').toString('base64');

    await execFileAsync(
      'powershell.exe',
      ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encodedCommand],
      {
        env: {
          ...process.env,
          SELRENA_TTS_TEXT: text,
          SELRENA_TTS_OUTPUT: outputPath,
        },
        windowsHide: true,
        maxBuffer: 1024 * 1024,
      },
    );

    return 'windows-sapi';
  }

  private createFallbackWav(durationMs: number): Buffer {
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
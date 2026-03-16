/**
 * Selrena 原生能力 C ABI 接口
 *
 * 该头文件仅声明接口，具体实现由不同平台的本地模块提供。
 * 目标是对外提供一个最简、稳定、跨语言的 C ABI。
 *
 * 对于项目本身，此头文件用于定义接口及其约定，并兼容在 TS/JS 或 Python 中通过 FFI 调用。
 */

#ifndef SELRENA_NATIVE_H
#define SELRENA_NATIVE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stddef.h>

// ====================== 错误码定义 ======================
typedef enum SelrenaResult {
    SELRENA_SUCCESS = 0,
    SELRENA_ERROR_UNKNOWN = -1,
    SELRENA_ERROR_INVALID_PARAM = -2,
    SELRENA_ERROR_MEMORY = -3,
    SELRENA_ERROR_MODEL_LOAD_FAILED = -4,
    SELRENA_ERROR_INFERENCE_FAILED = -5,
    SELRENA_ERROR_AUDIO_PROCESS_FAILED = -6,
} SelrenaResult;

// ====================== 音频格式定义 ======================
typedef struct SelrenaAudioFormat {
    int sample_rate;      // 采样率，单位 Hz
    int channels;         // 通道数
    int bits_per_sample;  // 位深
} SelrenaAudioFormat;

// ====================== 语音转文字（ASR）接口 ======================

/**
 * 初始化ASR模型
 * @param model_path 模型文件路径
 * @return 执行结果
 */
SelrenaResult selrena_asr_init(const char* model_path);

/**
 * 语音转文字
 * @param audio_data 音频数据指针
 * @param audio_length 音频数据长度（字节）
 * @param format 音频格式
 * @param out_text 输出文本缓冲区
 * @param out_text_max_length 输出缓冲区容量
 * @return 执行结果
 */
SelrenaResult selrena_asr_process(
    const uint8_t* audio_data,
    size_t audio_length,
    const SelrenaAudioFormat* format,
    char* out_text,
    size_t out_text_max_length
);

/**
 * 释放ASR模型资源
 */
void selrena_asr_free(void);

// ====================== 文字转语音（TTS）接口 ======================

/**
 * 初始化TTS模型
 * @param model_path 模型文件路径
 * @return 执行结果
 */
SelrenaResult selrena_tts_init(const char* model_path);

/**
 * 文字转语音
 * @param text 要转换的文字
 * @param out_audio_data 输出音频数据指针（由调用者释放）
 * @param out_audio_length 输出音频数据长度
 * @param out_format 输出音频格式
 * @return 执行结果
 */
SelrenaResult selrena_tts_process(
    const char* text,
    uint8_t** out_audio_data,
    size_t* out_audio_length,
    SelrenaAudioFormat* out_format
);

/**
 * 释放TTS生成的音频数据
 * @param audio_data 音频数据指针
 */
void selrena_tts_free_audio(uint8_t* audio_data);

/**
 * 释放TTS模型资源
 */
void selrena_tts_free(void);

#ifdef __cplusplus
}
#endif

#endif // SELRENA_NATIVE_H

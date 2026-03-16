#include "../include/selrena_native.h"
#include <stdlib.h>
#include <string.h>

// NOTE: This is a minimal stub implementation to satisfy build and linkage.
// Real model inference should be implemented in platform-specific native code.

static int is_asr_initialized = 0;
static int is_tts_initialized = 0;

SelrenaResult selrena_asr_init(const char* model_path) {
    (void)model_path;
    is_asr_initialized = 1;
    return SELRENA_SUCCESS;
}

SelrenaResult selrena_asr_process(
    const uint8_t* audio_data,
    size_t audio_length,
    const SelrenaAudioFormat* format,
    char* out_text,
    size_t out_text_max_length
) {
    if (!is_asr_initialized || !audio_data || audio_length == 0 || !out_text || out_text_max_length == 0) {
        return SELRENA_ERROR_INVALID_PARAM;
    }

    // Stub behavior: return fixed text
    const char* stub_result = "[ASR 模拟结果]";
    strncpy(out_text, stub_result, out_text_max_length - 1);
    out_text[out_text_max_length - 1] = '\0';
    (void)format;
    return SELRENA_SUCCESS;
}

void selrena_asr_free(void) {
    is_asr_initialized = 0;
}

SelrenaResult selrena_tts_init(const char* model_path) {
    (void)model_path;
    is_tts_initialized = 1;
    return SELRENA_SUCCESS;
}

SelrenaResult selrena_tts_process(
    const char* text,
    uint8_t** out_audio_data,
    size_t* out_audio_length,
    SelrenaAudioFormat* out_format
) {
    if (!is_tts_initialized || !text || !out_audio_data || !out_audio_length || !out_format) {
        return SELRENA_ERROR_INVALID_PARAM;
    }

    // Stub behavior: return silent audio (empty)
    *out_audio_length = 0;
    *out_audio_data = NULL;
    out_format->sample_rate = 16000;
    out_format->channels = 1;
    out_format->bits_per_sample = 16;
    (void)text;
    return SELRENA_SUCCESS;
}

void selrena_tts_free_audio(uint8_t* audio_data) {
    free(audio_data);
}

void selrena_tts_free(void) {
    is_tts_initialized = 0;
}

cmake_minimum_required(VERSION 3.20)
project(SelrenaNative)

# 跨平台编译配置
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# 区分Windows/Linux编译参数
if(WIN32)
    set(CMAKE_SHARED_LIBRARY_PREFIX "")  # Win下生成.dll而非libxxx.dll
    # Release优化
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /O2 /EHsc")
else()
    set(CMAKE_SHARED_LIBRARY_PREFIX "lib") # Linux下生成.so
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -pthread")
endif()

# 包含头文件
include_directories(include)
include_directories(gpt-sovits/include)
include_directories(funasr/include)
include_directories(llama.cpp/include)

# 编译GPT-SoVITS为共享库（TTS核心）
# 真实场景中，这里应指向 gpt-sovits 子模块的源文件
# 目前仅做结构占位，待用户 clone 实际代码后生效
# add_library(selrena_tts SHARED
#    gpt-sovits/src/tts_engine.cpp
#    gpt-sovits/src/ggml_inference.cpp
# )

# 编译FunASR为共享库（ASR核心）
# add_library(selrena_asr SHARED
#    funasr/src/asr_engine.cpp
#    funasr/src/onnx_inference.cpp
# )

# 编译llama.cpp为共享库（LLM核心）
# add_library(selrena_llm SHARED
#    llama.cpp/src/llama_engine.cpp
#    llama.cpp/src/gguf_inference.cpp
# )

# 链接依赖库（Win/Linux通用） - 暂时注释以防报错
# if(WIN32)
#     target_link_libraries(selrena_tts PRIVATE gpt-sovits/lib/ggml.lib)
#     target_link_libraries(selrena_asr PRIVATE funasr/lib/onnxruntime.lib)
#     target_link_libraries(selrena_llm PRIVATE llama.cpp/lib/llama.lib)
# else()
#     target_link_libraries(selrena_tts PRIVATE ggml pthread)
#     target_link_libraries(selrena_asr PRIVATE onnxruntime pthread)
#     target_link_libraries(selrena_llm PRIVATE llama pthread)
# endif()

# 输出目录：统一放到build目录
# set_target_properties(selrena_tts PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/build)
# set_target_properties(selrena_asr PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/build)
# set_target_properties(selrena_llm PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/build)


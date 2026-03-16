cmake_minimum_required(VERSION 3.16)
project(selrena_native C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# 输出目录
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# 包含头文件路径
include_directories(${CMAKE_SOURCE_DIR}/include)

# 源文件
set(SOURCES
    src/selrena_native.c
)

add_library(selrena_native SHARED ${SOURCES})

# 安装目标（可选）
install(TARGETS selrena_native
  RUNTIME DESTINATION bin
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib
)

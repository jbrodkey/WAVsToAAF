cmake_minimum_required(VERSION 3.10)
project(aaf_embedder)

set(CMAKE_CXX_STANDARD 17)

# Find AAF SDK
find_package(AAF REQUIRED)

add_executable(aaf_embedder main.cpp)

# Link AAF SDK
if(AAF_FOUND)
    target_include_directories(aaf_embedder PRIVATE ${AAF_INCLUDE_DIRS})
    target_link_libraries(aaf_embedder PRIVATE ${AAF_LIBRARIES})
else()
    message(FATAL_ERROR "AAF SDK not found. Please install and set AAF_DIR.")
endif()

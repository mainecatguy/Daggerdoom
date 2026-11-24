cmake_minimum_required(VERSION 3.15)
cmake_policy(SET CMP0091 NEW)
project(doomerfall_bridge CXX)

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

# The DLL that Daggerfall Unity loads. UZDoom and the launcher compile the same source directly.
add_library(doomerfall_bridge SHARED doomerfall_bridge.cpp doomerfall_bridge.h)
target_compile_features(doomerfall_bridge PRIVATE cxx_std_17)
target_compile_definitions(doomerfall_bridge PRIVATE DFB_BUILD_DLL)

add_executable(bridge_stress test/bridge_stress.cpp doomerfall_bridge.cpp)
target_compile_features(bridge_stress PRIVATE cxx_std_17)
target_include_directories(bridge_stress PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

include(BridgeBindings.cmake)
dfb_require_fresh_bindings(doomerfall_bridge)
dfb_require_fresh_bindings(bridge_stress)

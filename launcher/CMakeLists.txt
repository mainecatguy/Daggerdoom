cmake_minimum_required(VERSION 3.15)
cmake_policy(SET CMP0091 NEW)
project(doomerfall_launcher CXX)

add_executable(doomerfall-launcher WIN32 main.cpp)
target_compile_features(doomerfall-launcher PRIVATE cxx_std_17)
target_compile_definitions(doomerfall-launcher PRIVATE UNICODE _UNICODE)
target_link_libraries(doomerfall-launcher PRIVATE shell32 user32)
set_property(TARGET doomerfall-launcher PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

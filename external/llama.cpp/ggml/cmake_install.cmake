# Install script for directory: /mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/usr/local")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Install shared libraries without execute permission?
if(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  set(CMAKE_INSTALL_SO_NO_EXE "1")
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

# Set default install directory permissions.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/usr/bin/objdump")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for the subdirectory.
  include("/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/src/cmake_install.cmake")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml.so")
    file(RPATH_CHECK
         FILE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml.so"
         RPATH "")
  endif()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/bin/libggml.so")
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml.so")
    file(RPATH_CHANGE
         FILE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml.so"
         OLD_RPATH "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/bin:"
         NEW_RPATH "")
    if(CMAKE_INSTALL_DO_STRIP)
      execute_process(COMMAND "/usr/bin/strip" "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml.so")
    endif()
  endif()
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include" TYPE FILE FILES
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-cpu.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-alloc.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-backend.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-blas.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-cann.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-cpp.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-cuda.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-kompute.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-opt.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-metal.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-rpc.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-sycl.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/ggml-vulkan.h"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/include/gguf.h"
    )
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml-base.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml-base.so")
    file(RPATH_CHECK
         FILE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml-base.so"
         RPATH "")
  endif()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/bin/libggml-base.so")
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml-base.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml-base.so")
    if(CMAKE_INSTALL_DO_STRIP)
      execute_process(COMMAND "/usr/bin/strip" "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml-base.so")
    endif()
  endif()
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/cmake/ggml" TYPE FILE FILES
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/ggml-config.cmake"
    "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/llama.cpp/ggml/ggml-version.cmake"
    )
endif()


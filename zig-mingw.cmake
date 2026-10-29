# Cross-build Windows PuTTY with zig cc (no mingw install needed).
# build.py passes -DPUTTY_LAUNCHERS=<dir> holding the launchers it made.
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)
set(_b ${PUTTY_LAUNCHERS})
if(CMAKE_HOST_WIN32)
  set(_x .cmd)
else()
  set(_x "")
endif()
set(CMAKE_C_COMPILER   ${_b}/zig-cc${_x})
set(CMAKE_RC_COMPILER  ${_b}/zig-rc${_x})
set(CMAKE_AR           ${_b}/zig-ar${_x})
set(CMAKE_RANLIB       ${_b}/zig-ranlib${_x})
add_compile_definitions(__USE_MINGW_ANSI_STDIO)
# zig cc defines NDEBUG at -O2; PuTTY forbids it
add_compile_options(-UNDEBUG)
# zig cc ignores CMake's default GUI flag; set subsystem explicitly (else GUI exes open a console)
set(CMAKE_CREATE_WIN32_EXE -Wl,--subsystem,windows)

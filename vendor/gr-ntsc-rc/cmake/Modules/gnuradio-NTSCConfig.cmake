find_package(PkgConfig)

PKG_CHECK_MODULES(PC_GR_NTSC gnuradio-NTSC)

FIND_PATH(
    GR_NTSC_INCLUDE_DIRS
    NAMES gnuradio/NTSC/api.h
    HINTS $ENV{NTSC_DIR}/include
        ${PC_NTSC_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    GR_NTSC_LIBRARIES
    NAMES gnuradio-NTSC
    HINTS $ENV{NTSC_DIR}/lib
        ${PC_NTSC_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/gnuradio-NTSCTarget.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GR_NTSC DEFAULT_MSG GR_NTSC_LIBRARIES GR_NTSC_INCLUDE_DIRS)
MARK_AS_ADVANCED(GR_NTSC_LIBRARIES GR_NTSC_INCLUDE_DIRS)

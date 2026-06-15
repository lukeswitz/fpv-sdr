# Copyright 2020 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

########################################################################
# Check if there is C++ code at all
########################################################################
if(NOT NTSC_sources)
    MESSAGE(STATUS "No C++ sources... skipping python bindings")
    return()
endif(NOT NTSC_sources)

########################################################################
# Check for pygccxml
########################################################################
GR_PYTHON_CHECK_MODULE_RAW(
    "pygccxml"
    "import pygccxml"
    PYGCCXML_FOUND
    )

include(GrPybind)

########################################################################
# Python Bindings
########################################################################

list(APPEND NTSC_python_files
    decoder_c_python.cc
    transmitter_c_python.cc
    video_stream_converter_c_python.cc
    python_bindings.cc)

GR_PYBIND_MAKE_OOT(NTSC
   ../../..
   gr::NTSC
   "${NTSC_python_files}")

# copy in bindings .so file for use in QA test module
add_custom_target(
  copy_bindings_for_tests ALL
  COMMAND
    ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_BINARY_DIR}/*.so"
    ${CMAKE_BINARY_DIR}/test_modules/gnuradio/NTSC/
  DEPENDS NTSC_python)

install(TARGETS NTSC_python DESTINATION ${GR_PYTHON_DIR}/gnuradio/NTSC COMPONENT pythonapi)

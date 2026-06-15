#ifndef INCLUDED_NTSC_VIDEO_STREAM_CONVERTER_C_IMPL_H
#define INCLUDED_NTSC_VIDEO_STREAM_CONVERTER_C_IMPL_H
#include <gnuradio/NTSC/video_stream_converter_c.h>
#include "NTSC_configuration.h"
namespace gr {
  namespace NTSC {
    class video_stream_converter_c_impl : public video_stream_converter_c
    {



    /*-------------------GLOBAL VARS DEFINITION ------------------*/
     private:
       float d_decimation_factor;
       float d_img_mat[Y_HEIGHT + 20][X_WIDTH + 20];
       int d_x_in;
       int d_x_out;
       int d_y_in;
       int d_y_out;
       int d_bw_in;



     public:
      video_stream_converter_c_impl(float samp_rate, float decimation_factor);
      ~video_stream_converter_c_impl();
      int work(int noutput_items,
         gr_vector_const_void_star &input_items,
         gr_vector_void_star &output_items);
    };
  } // namespace NTSC
} // namespace gr
#endif

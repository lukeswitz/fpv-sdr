/*-------------------------NTSC VIDEO STREAM CONVERTER C++ -- -------------------*/
/*
/*      This block converts input streams from "NTSC Decoder C++" to the suitable
/* video stream for "Video SDL Link" and copes with the difference of rate.

--- INPUTS ---
    * in0 : Control signal of NTSC states : synchronisation, equalising, ...
        Note : NTSC_configuration.h lists all states.
    * in1 : X = position of the pixel over the x-axis, from 0 to 360.
    * in2 : Y = position of the pixel over the y-axis, from 0 to 240.
    * in3 : BW = black and white level of the pixel : from black = 0 to white = 255.
        Note : Inputs 1, 2, 3 are equal to -1 unless control signal out0 = video.

--- OUTPUT ---
    * out0 : grayscale level of the right pixel, from black = 0 to white = 255.
    As to dispaly the video correctly, the pixels order required by "Video SDL Sink" is handled by the decimation factor.

--- PARAMETERS ---
    * Sample Rate : samp_rate.
    * Decimation factor : Sample rate from samp_rate to samp_rate / decimation.
        Note : decimation = samp_rate / (x_width - y_height - frame_rate) = samp_rate / (360 * 240 * 30).

--- CODE DESCRIPTION ---
    The code processes inputs and output samples separately.
    On control signal in0 = video, input samples update the matrix representing the screen according to the pixel position and BW level.
    While the block outputs the right pixel BW level from the same matrix.
*/




#ifdef HAVE_CONFIG_H
#include "config.h"
#endif
#include <gnuradio/io_signature.h>
#include "video_stream_converter_c_impl.h"


/*-----------------------MY LIBRARIES-------------------*/
#include "NTSC_configuration.h"
#include <stdio.h>


namespace gr {
  namespace NTSC {
    video_stream_converter_c::sptr
    video_stream_converter_c::make(float samp_rate, float decimation_factor)
    {
      return gnuradio::get_initial_sptr
        (new video_stream_converter_c_impl(samp_rate, decimation_factor));
    }



    /*----------------------- CONSTRUCTOR -------------------*/
    video_stream_converter_c_impl::video_stream_converter_c_impl(float samp_rate, float decimation_factor)
      : gr::sync_decimator("video_stream_converter_c",
              gr::io_signature::make(4, 4, sizeof(float)),
              gr::io_signature::make(1, 1, sizeof(short)), decimation_factor)
    {
      /*** INIT ***/
      d_decimation_factor = decimation_factor;
      d_x_in = 0;
      d_y_in = 0;
      d_bw_in = 0;
      d_x_out = 0;
      d_y_out = 0;
			for(int i = 0; i < X_WIDTH; i++){
				for(int j = 0; j < Y_HEIGHT; j++)
					d_img_mat[j][i] = 127;
			}
      printf("Welcome in NTSC Video Stream Converter C++\n");
    }




    video_stream_converter_c_impl::~video_stream_converter_c_impl(){}
    int
    video_stream_converter_c_impl::work(int noutput_items,
        gr_vector_const_void_star &input_items,
        gr_vector_void_star &output_items)
    {



      /*-----------------------SIGNAL PROCESSING -------------------*/
      const float *in = (const float *) input_items[0];
      const float *in1 = (const float *) input_items[1];
      const float *in2 = (const float *) input_items[2];
      const float *in3 = (const float *) input_items[3];
      short *out = (short *) output_items[0];



      /*------------------------ INPUTS-------------------------*/
      const int ninput = noutput_items * decimation();
      for(int i = 0; i < ninput; i++){

        // Process only on Video Transmission
        if(in[i] == VIDEO){

          // Fetch and Control X, Y, BW
          d_x_in = int(in1[i]);
          d_y_in = int(in2[i]);
          d_bw_in = int(in3[i]);
          if(d_bw_in > 250) d_bw_in = 250;
          if(d_bw_in < 5) d_bw_in = 5;

          // Inputs update image matrix
          if(d_x_in < X_WIDTH - 2 && d_x_in > 2  && d_y_in < Y_HEIGHT - 2 && d_y_in > 2 ){
            d_img_mat[d_y_in][d_x_in] = d_bw_in;
          }
        }
      }



      /*------------------------ OUTPUT -----------------------*/
      for(int i = 0; i < noutput_items; i++){

        // Update position
        d_x_out++;
        if(d_x_out == X_WIDTH){
          d_x_out = 0;
          d_y_out++;
        }
        if(d_y_out == Y_HEIGHT){
          d_y_out = 0;
        }

        // Output correct pixel b&w level
        if(d_x_out < X_WIDTH && d_x_out > -1 && d_y_out < Y_HEIGHT && d_y_out > -1 )
          out[i] = d_img_mat[d_y_out][d_x_out];
      }



      return noutput_items;
    }
  } /* namespace NTSC */
} /* namespace gr */

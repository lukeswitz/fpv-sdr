/*----------------------- NTSC TRANSMITTER C++ -------------------*/
/*
/*        This block generates a black and white NTSC video signal f
/* from the image defined in the header file "image_matrix.h".

--- INPUT ---
    "image_matrix.h" defines the displayed image as a float img_mat[240][360].
    img_mat[y][x] =  BW level of the pixel at (X, Y). (From Black = 0.0 to White = 1.0)

--- OUTPUT ---
    * out0 : NTSC signal (c.f. protocol definition).

--- PARAMETERS ---
    * Sample Rate : samp_rate.

--- CODE DESCRIPTION ---
    The block generates the NTSC Signal using state machine (meta-state and sub-state).
    States defined in NTSC_Protocol_And_Signal_Description.jpg
*/



#ifdef HAVE_CONFIG_H
#include "config.h"
#endif
#include <gnuradio/io_signature.h>
#include "transmitter_c_impl.h"



/*----------------------- MY LIBRARIES-------------------*/
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include "NTSC_configuration.h"
#include "image_matrix.h"



namespace gr {
  namespace NTSC {
    transmitter_c::sptr
    transmitter_c::make(float samp_rate)
    {
      return gnuradio::get_initial_sptr
        (new transmitter_c_impl(samp_rate));
    }



    /*----------------------- CONSTRUCTOR ---------------------*/
    transmitter_c_impl::transmitter_c_impl(float samp_rate)
      : gr::sync_block("transmitter_c",
              gr::io_signature::make(0, 0, sizeof(float)),
              gr::io_signature::make(1, 1, sizeof(float)))
    {
      /*** INIT ***/
      d_samp_rate = samp_rate;
      d_meta_state = VERTICAL_SYNC;
      d_sub_state = EQUALISING;
      d_frame_parity = EVEN;
      d_samples_cnt = 0;
      d_lines_cnt = 0;
      printf("Welcome in NTSC Transmitter C++\n");
    }



    transmitter_c_impl::~transmitter_c_impl()
    {}
    int
    transmitter_c_impl::work(int noutput_items,
        gr_vector_const_void_star &input_items,
        gr_vector_void_star &output_items)
    {



      /*------------------ SIGNAL PROCESSING--------------------*/
      const float *in = (const float *) input_items[0];
      float *out = (float *) output_items[0];

      for(int i=0; i < noutput_items; i++){
        d_samples_cnt++;



        /*------------------- META STATE MACHINE -----------------*/
        if(d_meta_state == LINES_TRANSMISSION){


          /*---------------------- SUB STATE MACHINE -----------------*/

            /*** HORIZONTAL SYNCHRONISATION ***/
            if(d_sub_state == HORIZONTAL_SYNC){
              out[i] = HORIZONTAL_SYNC_LEVEL ;

              // Time for Back Porch
              if(d_samples_cnt > HORIZONTAL_SYNC_DURATION * d_samp_rate){
                d_sub_state = BACK_PORCH;
                d_samples_cnt = 0;
              }
            }


            /*** BACK PORCH ***/
            if(d_sub_state == BACK_PORCH){
              out[i] = BACK_PORCH_LEVEL;

              // Time for Active Video
              if(d_samples_cnt > BACK_PORCH_DURATION * d_samp_rate){
                d_sub_state = VIDEO;
                d_samples_cnt = 0;
              }
            }


            /*** ACTIVE VIDEO ***/
            if(d_sub_state == VIDEO){
              // Transmit pixel's black and white level from img_mat in image_matrix.h
              out[i] = BLACK_LEVEL + (WHITE_LEVEL - BLACK_LEVEL) * img_mat[int(d_lines_cnt )][int(360 * d_samples_cnt / (d_samp_rate * VIDEO_DURATION))] ;

              // Time for Front Porch
              if(d_samples_cnt > VIDEO_DURATION * d_samp_rate){
                d_sub_state = FRONT_PORCH;
                d_samples_cnt = 0;
              }
            }


            /*** FRONT PORCH ***/
            if(d_sub_state == FRONT_PORCH){
              out[i] = FRONT_PORCH_LEVEL;

              // Time for Horizontal Sync
              if(d_samples_cnt > FRONT_PORCH_DURATION * d_samp_rate){
                d_sub_state = HORIZONTAL_SYNC;
                d_samples_cnt = 0;
                d_lines_cnt++;
              }
            }

            // Exit to  Vertical Sync
            if(d_lines_cnt == NBR_VIDEO_LINES){
              d_meta_state = VERTICAL_SYNC;
              d_sub_state = EQUALISING;
              d_samples_cnt = 0;
              d_lines_cnt = 0;
            }
        }



        /*------------------- META STATE MACHINE -----------------*/
        if(d_meta_state == VERTICAL_SYNC){


          /*---------------------- SUB STATE MACHINE -----------------*/

          /*** EQUALISING_PULSES ***/
          if(d_sub_state == EQUALISING){

            // Set the Right Output
            if(d_samples_cnt < HORIZONTAL_SYNC_DURATION * d_samp_rate)
              out[i] = HORIZONTAL_SYNC_LEVEL;
            else
              out[i] = EQUALISING_LEVEL;

            // New Equalising Line
            if(d_samples_cnt > 0.5 * LINE_DURATION * d_samp_rate){
              d_samples_cnt = 0;
              d_lines_cnt += 0.5;
            }

            // Exit to Serration Lines for pre-equalising
            if(d_lines_cnt == NBR_EQUALISING_LINES){
              d_sub_state = SERRATION;
              d_samples_cnt = 0;
            }

            // Exit to SERRATION LINES for post-equalising
            if((d_lines_cnt == 3 * NBR_EQUALISING_LINES && d_frame_parity == ODD) ||
                (d_lines_cnt == 3 * NBR_EQUALISING_LINES - 0.5 && d_frame_parity == EVEN)){
              d_sub_state = BLANKING;
              d_samples_cnt = 0;
            }
          }


          /*** SERRATION PULSES ***/
          if(d_sub_state == SERRATION){

            // Set Right Output
            if(d_samples_cnt > (0.5 * LINE_DURATION - HORIZONTAL_SYNC_DURATION) * d_samp_rate)
              out[i] = EQUALISING_LEVEL;
            else
              out[i] = HORIZONTAL_SYNC_LEVEL;

            // New Serration Line
            if(d_samples_cnt > 0.5 * LINE_DURATION * d_samp_rate){
              d_samples_cnt = 0;
              d_lines_cnt += 0.5;
            }

            // Exit to Equalising Lines
            if(d_lines_cnt == 2 * NBR_EQUALISING_LINES){
              d_sub_state = EQUALISING;
              d_samples_cnt = 0;
            }
          }


          /*** BLANKING PULSES ***/
          if(d_sub_state == BLANKING){

            // Set Right Output
            if(d_samples_cnt < HORIZONTAL_SYNC_DURATION * d_samp_rate)
              out[i] = HORIZONTAL_SYNC_LEVEL;
            else
              out[i] = EQUALISING_LEVEL;

            // New Blanking Line
            if(d_samples_cnt > LINE_DURATION * d_samp_rate){
              d_samples_cnt = 0;
              d_lines_cnt++;
            }

            // Exit VERTICAL_SYNC YYY
            if((d_lines_cnt == NBR_VERTICAL_SYNC_LINES && d_frame_parity == ODD) ||
                (d_lines_cnt == NBR_VERTICAL_SYNC_LINES + 1.5 && d_frame_parity == EVEN)){
              d_meta_state = LINES_TRANSMISSION;
              d_sub_state = HORIZONTAL_SYNC;
              (d_frame_parity == EVEN) ? d_frame_parity = ODD : d_frame_parity = EVEN;
              d_samples_cnt = 0;
              d_lines_cnt = 0;
            }
          }
        }



      } // End of meta state machine
      return noutput_items; // End of signal processing
    }
  } /* namespace NTSC */
} /* namespace gr */

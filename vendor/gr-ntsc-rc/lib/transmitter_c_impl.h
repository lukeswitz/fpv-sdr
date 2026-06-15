#ifndef INCLUDED_NTSC_TRANSMITTER_C_IMPL_H
#define INCLUDED_NTSC_TRANSMITTER_C_IMPL_H
#include <gnuradio/NTSC/transmitter_c.h>
namespace gr {
  namespace NTSC {
    class transmitter_c_impl : public transmitter_c
    {



    /*----------------------- GLOBAL VARS DEFINITION -------------------*/
     private:
       float d_samp_rate;
       int d_samples_cnt;
       int d_meta_state;
       int d_sub_state;
       float d_lines_cnt;
       int d_frame_parity;



     public:
      transmitter_c_impl(float samp_rate);
      ~transmitter_c_impl();
      int work(int noutput_items,
         gr_vector_const_void_star &input_items,
         gr_vector_void_star &output_items);
    };
  } // namespace NTSC
} // namespace gr
#endif

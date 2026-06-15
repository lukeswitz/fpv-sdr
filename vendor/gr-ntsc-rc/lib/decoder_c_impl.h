#ifndef INCLUDED_NTSC_DECODER_C_IMPL_H
#define INCLUDED_NTSC_DECODER_C_IMPL_H
#include <gnuradio/NTSC/decoder_c.h>
namespace gr {
  namespace NTSC {
    class decoder_c_impl : public decoder_c
    {



     /*------------------ GLOBAL VAR DEFINITION -------------*/
     private:
      float d_samp_rate;
      float d_samples_cnt;
      float d_lines_cnt;
      int d_state;



     public:
      decoder_c_impl(float samp_rate);
      ~decoder_c_impl();
      int work(int noutput_items,
         gr_vector_const_void_star &input_items,
         gr_vector_void_star &output_items);
    };
  } // namespace NTSC
} // namespace gr
#endif

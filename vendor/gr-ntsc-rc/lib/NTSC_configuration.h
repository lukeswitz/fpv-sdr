/*---------------------NTSC_CONFIGURATION.H -------------------*/
/*
/*      This header file defines the charecteristic values of
/* NTSC Video Signal levels, timings and lines according to the protocol.
/* The states of signal (synchronisation, video, ...) are defined as code. */



/* -------------- NTSC SIGNAL TIMING (in sec.) ----------------*/
#define HORIZONTAL_SYNC_DURATION 4.7 * 0.000001
#define BACK_PORCH_DURATION 4.7  * 0.000001
#define VIDEO_DURATION 52.6  * 0.000001
#define FRONT_PORCH_DURATION 1.5 * 0.000001
#define LINE_DURATION 63.5 * 0.000001



/* ------------------- NTSC SIGNAL LEVELS ---------------------*/
#define BLACK_LEVEL -0.02
#define WHITE_LEVEL 0.06
#define HORIZONTAL_SYNC_THRESHOLD -0.020
#define HORIZONTAL_SYNC_LEVEL -0.04
#define BACK_PORCH_LEVEL -0.015
#define FRONT_PORCH_LEVEL -0.015
#define EQUALISING_LEVEL -0.015
#define VERTICAL_SYNC_LEVEL -0.04



/* -------------------- NTSC LINES FEATURES -------------------*/
#define NBR_VIDEO_LINES 240
#define NBR_EQUALISING_LINES 3
#define NBR_VERTICAL_SYNC_LINES 21
#define X_WIDTH 360
#define Y_HEIGHT 240



/* -------------------- NTSC SIGNAL STATES -------------------*/
#define IDLE 1
#define LINES_TRANSMISSION 2
#define FRONT_PORCH 3
#define HORIZONTAL_SYNC 4
#define BACK_PORCH 5
#define VIDEO 6
#define VERTICAL_SYNC 7
#define EQUALISING 8
#define SERRATION 9
#define BLANKING 10
#define EVEN 1
#define ODD 0

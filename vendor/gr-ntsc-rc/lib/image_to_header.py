#!/usr/bin/python
#------------------ IMAGE TO HEADER ---------------------
#
#   Converts a color image into a grayscale matrix defined
# in the header file : 'image_matrix.h".



# --------------------- LIBRARIES ----------------------
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
def rgb2gray(rgb):
    return np.dot(rgb[...,:3], [0.299, 0.587, 0.114])



# --------------- IMAGE FILE TO MATRIX  -----------------
img = mpimg.imread('./image1.jpg')
gray = rgb2gray(img)
gray = gray / 255



# ---------------- MATRIX TO STRING ----------------------
foo_str = "float img_mat[240][360] = {"
for y in range(240):
    foo_str += "{"
    for x in range(360):
        foo_str += str(gray[y][x]) + ", "
    foo_str = foo_str[:len(foo_str) - 2]
    foo_str += "}, "
foo_str = foo_str[:len(foo_str) - 2]
foo_str += "};"



#--------------- WRITE HEADER FILE ---------------
f = open('image_matrix.h', 'w')
f.write(foo_str)
f.close()

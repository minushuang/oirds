
#!/usr/bin/env python
# Used to build the training images for a labeled data set.
# each training image is black (0,0,0).  The polygons representing each label
# has an assigned color in the image.


import matplotlib 
matplotlib.use('Agg') 
import lmdb
from PIL import Image
import gt_tool
import json_tools

def main():
    import os
    import shutil
    import glob
    import sys
    import random
    if sys.version_info[0] < 3:
        from StringIO import StringIO
    else:
        from io import StringIO

    if len(sys.argv) < 1:
      print "Usage: ", sys.argv[0], " config"
      sys.exit( 0 )

    if (os.path.isdir("./png_gt")):
      shutil.rmtree("./png_gt")
    if (os.path.isdir("./png_raw")):
      shutil.rmtree("./png_raw")
    if (os.path.isdir("./raw_train")):
      shutil.rmtree("./raw_train")
    if (os.path.isdir("./raw_test")):
      shutil.rmtree("./raw_test")
    if (os.path.isdir("./groundtruth_train")):
      shutil.rmtree("./groundtruth_train")
    if (os.path.isdir("./groundtruth_test")):
      shutil.rmtree("./groundtruth_test")

    os.mkdir("./png_gt",0755)
    os.mkdir("./png_raw",0755)

    config = json_tools.loadConfig(sys.argv[1])

    gtTool = gt_tool.GTTool(config)
    gtTool.load()
   
    randUniform = random.seed(23361)

    out_db_train = lmdb.open('raw_train', map_size=int(4294967296))
    out_db_test = lmdb.open('raw_test', map_size=int(4294967296))
    label_db_train = lmdb.open('groundtruth_train', map_size=int(4294967296))
    label_db_test = lmdb.open('groundtruth_test', map_size=int(4294967296))

    testSlice = json_tools.getTestSlice(config) if json_tools.hasTestSlice(config)  else None
    testNames = gtTool.getTestNames(json_tools.getPercentageForTest(config), testSlice)

    with out_db_train.begin(write=True) as odn_txn:
     with out_db_test.begin(write=True) as ods_txn:
      with label_db_train.begin(write=True) as ldn_txn:
       with label_db_test.begin(write=True) as lds_txn:
         writeOutImages(gtTool, odn_txn, ods_txn, ldn_txn, lds_txn, testNames, config)

    out_db_train.close()
    label_db_train.close()
    out_db_test.close()
    label_db_test.close()
    sys.exit(0)

def  writeOutImages(gtTool, odn_txn, ods_txn, ldn_txn, lds_txn, testNames, config):
    test_idx = [0]
    train_idx = [0]
    def f(lastname, lastList):
        idxUpdates = outputImages(lastname, lastList, gtTool, odn_txn, ods_txn, ldn_txn, lds_txn, testNames, test_idx[0], train_idx[0],config)
        test_idx[0] = test_idx[0] +  idxUpdates[1]
        train_idx[0] = train_idx[0] +  idxUpdates[0]
    gtTool.iterate(f)

def echoFunction(x):
  return x

def rotateFunction(degrees, imset):
  return imset.rotate(degrees)

def getAugmentFunctions(config):
  from functools import partial
  return [echoFunction, partial(rotateFunction,90),partial(rotateFunction,180),partial(rotateFunction,270)]

def outputImages(name, imageData, gtTool, odn_txn, ods_txn, ldn_txn, lds_txn, testNames, test_idx, train_idx,config):
   print name + '-----------'
   c = 0;
   imSet = createImgSet(name, imageData, gtTool, config)
   imageCropSize = json_tools.getCropSize(config)
   slide = json_tools.getSlide(config)
   if (imageCropSize == 0):
     imageCropSize = min(imSet.getImgShape()[0], imSet.getImgShape()[1])
   imageResize = imageCropSize
   if (json_tools.isResize(config)):
      imageResize = json_tools.getResize(config)
   if (imSet.getImgShape()[0] < imageCropSize or imSet.getImgShape()[1] < imageCropSize):
      print 'skipping'
      return (0,0)
   augmentFunctions = getAugmentFunctions(config)
   for croppedImSet in imSet.imageSetFromCroppedImage(imageCropSize, slide):
     if (imageResize != croppedImSet.getImgShape()[0]):
        croppedImSet = croppedImSet.resize(imageResize)
     for augmentFunction in augmentFunctions:
        augmentedImSet = augmentFunction(croppedImSet)
        labelImage, labelIndices, centers = augmentedImSet.placePolysInImage()
        rawImage = augmentedImSet.rawImage
        labelImage.save("./png_gt/" + name[0:name.rindex('.')] + "_" + str(c) + ".png")
        rawImage.save("./png_raw/"  + name[0:name.rindex('.')] + "_" + str(c) + ".png")
        c += 1
        if (name in testNames):
           outGT(rawImage, ods_txn, test_idx + c)
           outGTLabel(labelIndices, lds_txn, test_idx+c)
        else:
           outGT(rawImage, odn_txn, train_idx + c)
           outGTLabel(labelIndices, ldn_txn, train_idx+c)
   return (0,c) if (name in testNames) else (c,0)


def createImgSet(name, xlsInfoList, gtTool, config):
  imRaw= gtTool.loadImage(name)
  return gtTool.createImageSet(xlsInfoList, imRaw, json_tools.getSingleLabel(config))
   
def outGT (im, out_txn, idx):
   import caffe
   import numpy as np
   tmp = np.array(im)
   tmp= tmp[:,:,::-1]
   tmp = tmp.transpose((2,0,1))
   im_dat = caffe.io.array_to_datum(tmp)
   out_txn.put('{:0>10d}'.format(idx), im_dat.SerializeToString())

def outGTLabel (imArray, out_txn, idx):
   import caffe
   import numpy as np
   im_dat = caffe.io.array_to_datum(imArray)
   out_txn.put('{:0>10d}'.format(idx), im_dat.SerializeToString())

if __name__=="__main__":
    main()


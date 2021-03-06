#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 19 06:21:16 2017

@author: zhaoy
"""

import numpy as np
import cv2
import os
import os.path as osp
import sys

import argparse

# reload(sys)
# sys.setdefaultencoding("utf-8")
os.environ['GLOG_minloglevel'] = '2'  # suppress log

import _init_paths
# from matplotlib import pyplot as plt
from mtcnn_aligner import MtcnnAligner

from fx_warp_and_crop_face import get_reference_facial_points, warp_and_crop_face


output_size = (112, 112)
default_square = True
inner_padding_factor = 0
outer_padding = (0, 0)

reference_5pts = get_reference_facial_points(output_size,
                                                inner_padding_factor,
                                                outer_padding,
                                                default_square)


def parse_args():
    parser = argparse.ArgumentParser(description='face alignment by MTCNN')
    # general
    parser.add_argument('--image-list', default='',
                        help='')
    parser.add_argument('--image-root-dir', default='',
                        help='')
    parser.add_argument('--rect-root-dir', default='',
                        help='')
    parser.add_argument('--mtcnn-model-dir', default='../../model',
                        help='')
    parser.add_argument('--save-dir', default='./aligned_root_dir',
                        help='')
    parser.add_argument('--gpu-id', type=int, default=0,
                        help='')
    parser.add_argument('--nsplits', type=int, default=1,
                        help='how many splits to split the image-list into')
    parser.add_argument('--split-id', type=int, default=0,
                        help='which split to process in current program process')
    args = parser.parse_args()
    return args

'''
{"box": {"top": 1692, "right": 4589, "left": 4399, "bottom": 1878}
'''

def get_gt_rect(rect_fn):
    fp = open(rect_fn, 'r')
    facex_det_resp=json.load(fp)
    rects=[]
    js_str = json.dumps(facex_det_resp, indent=4)
    print facex_det_resp
    if(not facex_det_resp
        or facex_det_resp['code']
        or 'result' not in facex_det_resp
        or 'detections' not in facex_det_resp['result']
        or len(facex_det_resp['result']['detections']) < 1
        ):
            print '--->facex-det failed or no face detected '
            return [] 
    faces = facex_det_resp['result']['detections']
    print '\n--->%d faces detected' % len(faces)
    # facex-det request data
    for face_idx, face in enumerate(faces):
        print '\n--->process face #%d' % face_idx
        # facex-[age, gender, feature] request data
        bbox=face['pts']
        t_array = np.array(bbox) 
        # if t_array.shape == (4, 2):
        #     t_array = t_array[(0,2), ...]
        # elif t_array.size == 4:
        #     t_array = t_array.reshape((2, 2))
        if t_array.shape == (4, 2):
            xmin,ymin=t_array[0]
            xmax,ymax=t_array[2]
            rect = [xmin, ymin, xmax, ymax]
            print 'rect--->',rect
            rects.append(rect)
           
    
    return rects

def rename_with_folderName(str_path):
    last_flag=str_path.rfind('/')
    filename=str_path[last_flag+1:]
    print 'filename',filename
    temp=str_path[:last_flag]
    flag=temp.rfind('/')
    foldername=temp[flag+1:]
    print foldername + "_" + filename
    return foldername + "_" + filename



def main(args):
    save_dir = args.save_dir
    list_file = args.image_list
    nsplits = args.nsplits
    split_id = args.split_id
    mtcnn_model_dir = args.mtcnn_model_dir
    img_root_dir = args.image_root_dir
    rect_root_dir = args.rect_root_dir
    gpu_id = args.gpu_id

    if not save_dir:
        save_dir = './aligned_root_dir'

    if not osp.exists(save_dir):
        print('makedirs for aligned root dir: ', save_dir)
        os.makedirs(save_dir)

    save_aligned_dir = osp.join(save_dir, 'aligned_imgs')
    if not osp.exists(save_aligned_dir):
        print('makedirs for aligned/cropped face imgs: ', save_dir)
        os.makedirs(save_aligned_dir)

    save_rects_dir = osp.join(save_dir, 'face_rects')
    if not osp.exists(save_rects_dir):
        print('makedirs for face rects/landmarks: ', save_rects_dir)
        os.makedirs(save_rects_dir)

    aligner = MtcnnAligner(mtcnn_model_dir, True, gpu_id=gpu_id)

    fp = open(list_file, 'r')
    all_lines = fp.readlines()
    fp.close()

    total_line_cnt = len(all_lines)
    print('--->%d imgs in total' % total_line_cnt)

    if nsplits < 2:
        if split_id > 0:
            print('===> Will only process first %d imgs' % split_id)
            start_line = 0
            end_line = split_id
        else:
            print('===> Will process all of the images')
            start_line = 0
            end_line = total_line_cnt
    else:
        assert(split_id < nsplits)
        lines_per_split = float(total_line_cnt) / nsplits
        start_line = int(lines_per_split * split_id)
        end_line = int(lines_per_split * (split_id + 1))
        if end_line + 1 >= total_line_cnt:
            end_line = total_line_cnt

        print('===> Will only process imgs in the range [%d, %d)]' % (
            start_line, end_line))

    count = start_line

    all_lines = all_lines[start_line:end_line]

    for line in all_lines:
        line = line.strip()
        print '%d\n' % count

        count = count + 1
        # img_fn = osp.join(img_root_dir, line)
        img_fn=line
        print('===> Processing img: ' + img_fn)
        img = cv2.imread(img_fn)
        ht = img.shape[0]
        wd = img.shape[1]

        print 'image.shape:', img.shape

        rect_fn =  osp.join(rect_root_dir,rename_with_folderName(line) + '.json')  #osp.join(rect_root_dir,line[0:-4] + '.json')
        gt_rect = get_gt_rect(rect_fn)
        if gt_rect is None:
            print('Failed to get_gt_rect(), skip to next image')
            continue

        # print 'face rect: ', gt
        boxes, points = aligner.align_face(img, [gt_rect])
        assert len(boxes)==len(points)
        for i in range(len(boxes)):
            box = boxes[i]
            pts = points[i]

            spl = osp.split(line)
            sub_dir = spl[0]
            base_name = spl[-1]

            save_img_subdir = osp.join(save_aligned_dir, sub_dir)
            if not osp.exists(save_img_subdir):
                os.makedirs(save_img_subdir)

            save_rect_subdir = osp.join(save_rects_dir, sub_dir)
            if not osp.exists(save_rect_subdir):
                os.makedirs(save_rect_subdir)
            # print pts

            save_img_fn = osp.join(save_img_subdir, base_name)

            facial5points = np.reshape(pts, (2, -1))
            dst_img = warp_and_crop_face(
                img, facial5points, reference_5pts, output_size)
            cv2.imwrite(save_img_fn, dst_img)

            save_rect_fn = osp.join(
                save_rect_subdir, osp.splitext(base_name)[0] + '.txt')
            fp_rect = open(save_rect_fn, 'w')
            for it in box:
                fp_rect.write('%5.2f\t' % it)
            fp_rect.write('\n')

            for i in range(5):
                fp_rect.write('%5.2f\t%5.2f\n' %
                            (facial5points[0][i], facial5points[1][i]))
            fp_rect.close()

'''
if __name__ == "__main__":
    args = parse_args()
    main(args)
'''

if __name__ == "__main__":
      rect_fn="test.json"
      gt_rect = get_gt_rect(rect_fn)
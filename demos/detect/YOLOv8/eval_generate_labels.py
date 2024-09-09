#!/user/bin/env python

# Copyright (c) 2024，WuChao D-Robotics.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# 注意: 此程序在RDK板端运行
# Attention: This program runs on RDK board.

from YOLOv8_Detect import *

import json

import argparse
import logging 
import os
import gc


# 日志模块配置
# logging configs
logging.basicConfig(
    level = logging.DEBUG,
    format = '[%(name)s] [%(asctime)s.%(msecs)03d] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S')
logger = logging.getLogger("RDK_YOLO")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', type=str, default='models/patch_yolov8n_detect_bayese_640x640_nv12_modified.bin', 
                        help="""Path to BPU Quantized *.bin Model.
                                RDK X3(Module): Bernoulli2.  
                                RDK Ultra: Bayes.  
                                RDK X5(Module): Bayes-e.  
                                RDK S100: Nash-e.  
                                RDK S100P: Nash-m.""") 
    parser.add_argument('--classes-num', type=int, default=80, help='Classes Num to Detect.')
    parser.add_argument('--reg', type=int, default=16, help='DFL reg layer.')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='IoU threshold.')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='confidence threshold.')
    parser.add_argument('--image-path', type=str, default="../../../resource/DataSets/COCO2017_Val/val2017", help='COCO2017 val source image path.')
    parser.add_argument('--result-image-dump', type=bool, default=False, help='dump image result or not')
    parser.add_argument('--result-image-path', type=str, default="coco2017_image_result", help='COCO2017 val image result saving path.')
    parser.add_argument('--json-path', type=str, default="patch_yolov8n_coco2017_val_pridect.json", help='convert to json save path.')
    parser.add_argument('--max-num', type=int, default=50000, help='max num of images which will be precessed.')
    opt = parser.parse_args()
    logger.info(opt)

    # 实例化
    model = YOLOv8_Detect(opt.model_path, opt.conf_thres, opt.iou_thres)

    # 创建 result* 目录存储结果
    if opt.result_image_dump:
        for i in range(9999):
            result_image_path = f"{opt.result_image_path}_{i}"
            if not os.path.exists(result_image_path):
                os.makedirs(result_image_path)
                logger.info("\033[1;32m" + f"Created directory Successfully: \"{result_image_path}\"" + "\033[0m")
                break
    
    # 生成pycocotools的预测结果json文件
    pridect_json = []

    # 板端直接推理所有验证集，并生成标签和渲染结果 (串行程序)
    img_names = os.listdir(opt.image_path)
    img_num = len(img_names)
    control = opt.max_num
    for cnt, img_name in enumerate(img_names, 1):
        # 流程控制
        if control < 1:
            break
        control -= 1

        logger.info("\033[1;32m" + f"[{cnt}/{img_num}] Processing image: \"{img_name}\"" + "\033[0m")
        # 端到端推理
        img = cv2.imread(os.path.join(opt.image_path, img_name))
        input_tensor = model.bgr2nv12(img)

        outputs = model.c2numpy(model.forward(input_tensor))
        ids, scores, bboxes = model.postProcess(outputs)
        # 渲染结果并保存
        if opt.result_image_dump:
            logger.info("\033[1;32m" + "Draw Results: " + "\033[0m")
            for class_id, score, bbox in zip(ids, scores, bboxes):
                x1, y1, x2, y2 = bbox
                logger.info("(%d, %d, %d, %d) -> %s: %.2f"%(x1,y1,x2,y2, coco_names[class_id], score))
                draw_detection(img, (x1, y1, x2, y2), score, class_id)
                save_path = os.path.join(result_image_path, img_name[:-4] + "_result.jpg")
                cv2.imwrite(save_path, img)
                logger.info("\033[1;32m" + f"result image saved: \"./{save_path}\"" + "\033[0m")
        id_cnt = 0
        for class_id, score, bbox in zip(ids, scores, bboxes):
            x1, y1, x2, y2 = bbox
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)
            x1, y1, x2, y2, width, height = float(x1), float(y1), float(x2), float(y2), float(width), float(height)
            pridect_json.append({
                    'area': width * height,
                    'bbox': [x1, y1, width, height],
                    'category_id': int(class_id+1),
                    'id': id_cnt,
                    "score": float(score),
                    'image_id': int(img_name[:-4]),
                })
            id_cnt += 1

    # 保存标签
    with open(opt.json_path, 'w') as f:
        json.dump(pridect_json, f, ensure_ascii=False, indent=1)
    
    logger.info("\033[1;32m" + f"result label saved: \"{opt.json_path}\"" + "\033[0m")
    

if __name__ == "__main__":
    main()
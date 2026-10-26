# -*- coding: utf-8 -*-
"""全局配置：仙八色鸫（Fairy Pitta, 学名 Pitta nympha）图像识别。
所有脚本都从这里读参数，改一处即可全局生效。
"""
import os

# ---- 识别类别：目前只做仙八色鸫一类，以后加鸟种直接往 names 里追加 ----
NAMES = ["fairy_pitta"]

# ---- 检测参数 ----
IMG_SIZE = 320        # 训练/推理统一输入尺寸；320 是 PYNQ-Z2 能扛住的尺寸
CONF_THRES = 0.52     # 置信度阈值：误报多就调高(0.6)，漏检多就调低(0.3)
IOU_THRES = 0.45      # NMS 的 IoU 阈值，一般不用动

# ---- 与声音组的"唯一接口"：两个目录 ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRIGGER_DIR = os.path.join(BASE_DIR, "runtime", "trigger")   # 声音组往这里写触发文件
RESULT_DIR = os.path.join(BASE_DIR, "runtime", "result")     # 我们往这里写识别结果
ANNO_DIR = os.path.join(BASE_DIR, "runtime", "annotated")    # 画框后的截图
TRIGGER_FILE = "pitta.trigger"                               # 双方约定死的文件名

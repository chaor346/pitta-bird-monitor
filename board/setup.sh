#!/bin/bash
# 板端环境一键配置。用法: sudo bash setup.sh
set -e

echo "=== 配置 PYNQ-Z2 运行环境 ==="

echo "[1/4] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq ffmpeg v4l-utils python3-pip libopencv-dev

echo "[2/4] 安装 Python 依赖..."
pip3 install numpy pynq opencv-python-headless

echo "[3/4] 创建运行目录..."
mkdir -p /home/xilinx/runtime/trigger
mkdir -p /home/xilinx/runtime/annotated
mkdir -p /home/xilinx/runtime/videos
mkdir -p /home/xilinx/runtime/videos/_work

echo "[4/4] 配置摄像头权限..."
chmod 666 /dev/video0 2>/dev/null || echo "警告: /dev/video0 不存在"

if [ -f /home/xilinx/infer_ncnn.cpp ]; then
    echo "编译 ncnn 推理程序..."
    g++ -O2 -o /home/xilinx/infer_ncnn /home/xilinx/infer_ncnn.cpp \
        -lncnn -lopencv_core -lopencv_imgproc -lopencv_imgcodecs \
        || echo "警告: ncnn 编译失败"
fi

echo "=== 完成 ==="
echo "正式部署:"
echo "  sudo cp pitta-vision.service pitta-audio.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now pitta-vision pitta-audio"

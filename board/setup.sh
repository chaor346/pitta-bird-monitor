#!/bin/bash
# 板端环境一键配置脚本
# 用法: sudo bash setup.sh

set -e

echo "=== 配置 PYNQ-Z2 运行环境 ==="

# 1. 安装系统依赖
echo "[1/4] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq ffmpeg v4l-utils python3-pip libopencv-dev

# 2. 安装 Python 依赖
echo "[2/4] 安装 Python 依赖..."
pip3 install numpy pynq opencv-python-headless

# 3. 创建运行目录
echo "[3/4] 创建运行目录..."
mkdir -p /home/xilinx/runtime/trigger
mkdir -p /home/xilinx/runtime/annotated
mkdir -p /home/xilinx/runtime/videos
mkdir -p /home/xilinx/runtime/videos/_work

# 4. 配置摄像头权限（每次重启后需要）
echo "[4/4] 配置摄像头权限..."
chmod 666 /dev/video0 2>/dev/null || echo "警告: /dev/video0 不存在，请检查摄像头"

# 编译 ncnn 推理程序
if [ -f /home/xilinx/infer_ncnn.cpp ]; then
    echo "编译 ncnn 推理程序..."
    g++ -O2 -o /home/xilinx/infer_ncnn /home/xilinx/infer_ncnn.cpp \
        -lncnn -lopencv_core -lopencv_imgproc -lopencv_imgcodecs 2>/dev/null \
        || echo "警告: ncnn 编译失败，请检查 ncnn 库是否安装"
fi

echo "=== 环境配置完成 ==="
echo "下一步（正式部署，推荐：systemd 开机自启 + 崩溃拉起）:"
echo "  sudo cp pitta-audio.service pitta-vision.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now pitta-vision pitta-audio"
echo "  # 两个 unit 都 Requires=pl_server.service（PYNQ 镜像自带），缺失会启动失败"
echo ""
echo "手动调试（旧脚本，阈值 0.5，仅演示用）:"
echo "  终端1: bash start_audio.sh"
echo "  终端2: bash start_vision.sh"

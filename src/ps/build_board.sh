#!/bin/bash
# PYNQ-Z2 板端一键构建：编译 ncnn 库 + 图像推理 + 声音推理
# 用法: bash build_board.sh
set -e

echo "=== 1. 解压 ncnn 源码 ==="
if [ ! -d "ncnn-20240410" ]; then
    tar xzf ncnn_src.tar.gz
fi

echo "=== 2. 编译 ncnn 库 (约15-30分钟) ==="
cd ncnn-20240410
mkdir -p build && cd build
cmake .. \
    -DNCNN_BUILD_EXAMPLES=OFF \
    -DNCNN_BUILD_TOOLS=OFF \
    -DNCNN_BUILD_BENCHMARK=OFF \
    -DNCNN_OPENMP=ON \
    -DNCNN_RUNTIME_CPU=ON \
    -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -3
make -j2 2>&1 | tail -5
echo "ncnn 编译完成"
cd ../../

NCNN_INC="-I ncnn-20240410/src -I ncnn-20240410/build/src"
NCNN_LIB="-L ncnn-20240410/build/src -lncnn -fopenmp"

echo "=== 3. 编译图像推理 infer_ncnn ==="
g++ infer_ncnn.cpp -o infer_ncnn $NCNN_INC $NCNN_LIB -std=c++11 \
    `pkg-config --cflags --libs opencv` 2>/dev/null || \
g++ infer_ncnn.cpp -o infer_ncnn $NCNN_INC $NCNN_LIB -std=c++11 \
    -lopencv_core -lopencv_imgproc -lopencv_imgcodecs
echo "  infer_ncnn: $(ls -la infer_ncnn | awk '{print $5}') bytes"

echo "=== 4. 编译声音推理 sound_infer_ncnn ==="
g++ sound_infer_ncnn.cpp -o sound_infer_ncnn $NCNN_INC $NCNN_LIB -std=c++11
echo "  sound_infer_ncnn: $(ls -la sound_infer_ncnn | awk '{print $5}') bytes"

echo "=== 完成 ==="
echo "图像测试: ./infer_ncnn . bird.jpg"
echo "声音测试: python3 sound_board.py --once"

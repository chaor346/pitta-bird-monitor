// PYNQ-Z2 板端推理：ncnn + OpenCV，输出 JSON 到 stdout
// 单次模式: infer_ncnn <模型目录> <图片路径> [conf] [iou]
// 常驻模式: infer_ncnn --daemon <模型目录> [conf] [iou]
//           stdin每行一个图片路径, "quit"退出; stdout每行一个JSON
// 编译: g++ infer_ncnn.cpp -o infer_ncnn -I ncnn/src/includes -L ncnn/build/src -lncnn -lopencv_core -lopencv_imgproc -lopencv_imgcodecs -fopenmp -std=c++11
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <algorithm>
#include <string>
#include <iostream>
#include <opencv2/opencv.hpp>
#include "net.h"

#define IMG_SIZE 320
#define CLASS_NAME "fairy_pitta"

struct Box {
    float x1, y1, x2, y2, conf;
};

static float iou(const Box& a, const Box& b) {
    float x1 = std::max(a.x1, b.x1);
    float y1 = std::max(a.y1, b.y1);
    float x2 = std::min(a.x2, b.x2);
    float y2 = std::min(a.y2, b.y2);
    float inter = std::max(0.f, x2 - x1) * std::max(0.f, y2 - y1);
    float area_a = (a.x2 - a.x1) * (a.y2 - a.y1);
    float area_b = (b.x2 - b.x1) * (b.y2 - b.y1);
    return inter / (area_a + area_b - inter + 1e-6f);
}

static std::vector<Box> nms(std::vector<Box>& boxes, float iou_thres) {
    std::sort(boxes.begin(), boxes.end(), [](const Box& a, const Box& b) { return a.conf > b.conf; });
    std::vector<Box> keep;
    std::vector<bool> suppressed(boxes.size(), false);
    for (size_t i = 0; i < boxes.size(); i++) {
        if (suppressed[i]) continue;
        keep.push_back(boxes[i]);
        for (size_t j = i + 1; j < boxes.size(); j++) {
            if (suppressed[j]) continue;
            if (iou(boxes[i], boxes[j]) > iou_thres) suppressed[j] = true;
        }
    }
    return keep;
}

// 推理单帧, 返回JSON字符串(紧凑单行)
static std::string infer_image(ncnn::Net& net, const std::string& img_path,
                                float conf_thres, float iou_thres) {
    cv::Mat img = cv::imread(img_path);
    if (img.empty()) {
        return "{\"error\":\"无法读取图片\"}";
    }
    int orig_w = img.cols, orig_h = img.rows;

    // 预处理
    cv::Mat rgb;
    cv::cvtColor(img, rgb, cv::COLOR_BGR2RGB);
    ncnn::Mat in = ncnn::Mat::from_pixels_resize(
        rgb.data, ncnn::Mat::PIXEL_RGB, rgb.cols, rgb.rows, IMG_SIZE, IMG_SIZE);
    float norm[3] = {1/255.f, 1/255.f, 1/255.f};
    in.substract_mean_normalize(0, norm);

    // 推理
    ncnn::Extractor ex = net.create_extractor();
    ex.input("images", in);
    double t0 = (double)cv::getTickCount();
    ncnn::Mat out;
    ex.extract("output0", out);
    double dt = ((double)cv::getTickCount() - t0) / cv::getTickFrequency() * 1000;

    // 后处理
    std::vector<Box> boxes;
    const int num_anchors = out.w;
    for (int i = 0; i < num_anchors; i++) {
        float conf = out.row(4)[i];
        if (conf < conf_thres) continue;
        float cx = out.row(0)[i] * orig_w / IMG_SIZE;
        float cy = out.row(1)[i] * orig_h / IMG_SIZE;
        float bw = out.row(2)[i] * orig_w / IMG_SIZE;
        float bh = out.row(3)[i] * orig_h / IMG_SIZE;
        boxes.push_back({cx - bw/2, cy - bh/2, cx + bw/2, cy + bh/2, conf});
    }
    boxes = nms(boxes, iou_thres);

    // 紧凑JSON单行输出
    char buf[256];
    std::string json = "{";
    snprintf(buf, sizeof(buf), "\"infer_ms\":%.1f,\"found\":%s,\"count\":%d,\"boxes\":[",
             dt, boxes.empty() ? "false" : "true", (int)boxes.size());
    json += buf;
    for (size_t i = 0; i < boxes.size(); i++) {
        snprintf(buf, sizeof(buf), "{\"cls\":\"%s\",\"conf\":%.3f,\"box\":[%.1f,%.1f,%.1f,%.1f]}%s",
                 CLASS_NAME, boxes[i].conf, boxes[i].x1, boxes[i].y1, boxes[i].x2, boxes[i].y2,
                 i + 1 < boxes.size() ? "," : "");
        json += buf;
    }
    json += "]}";
    return json;
}

int main(int argc, char** argv) {
    // 常驻模式: --daemon <模型目录> [conf] [iou]
    if (argc >= 3 && std::string(argv[1]) == "--daemon") {
        std::string model_dir = argv[2];
        float conf_thres = argc > 3 ? atof(argv[3]) : 0.52f;
        float iou_thres = argc > 4 ? atof(argv[4]) : 0.45f;

        ncnn::Net net;
        net.opt.num_threads = 2;
        if (net.load_param((model_dir + "/best_ncnn.param").c_str()) != 0 ||
            net.load_model((model_dir + "/best_ncnn.bin").c_str()) != 0) {
            fprintf(stderr, "加载模型失败\n");
            return 1;
        }
        fprintf(stderr, "[daemon] 模型已加载, conf=%.3f, 等待图片路径...\n", conf_thres);

        std::string line;
        while (std::getline(std::cin, line)) {
            // 去掉首尾空白
            size_t s = line.find_first_not_of(" \t\r\n");
            if (s == std::string::npos) continue;
            size_t e = line.find_last_not_of(" \t\r\n");
            std::string path = line.substr(s, e - s + 1);
            if (path == "quit" || path == "exit") break;

            std::string json = infer_image(net, path, conf_thres, iou_thres);
            std::cout << json << std::endl;  // 每行一个JSON
            std::cout.flush();
        }
        fprintf(stderr, "[daemon] 退出\n");
        return 0;
    }

    // 单次模式: <模型目录> <图片路径> [conf] [iou]
    if (argc < 3) {
        fprintf(stderr, "用法: %s <模型目录> <图片路径> [conf] [iou]\n"
                        "  或: %s --daemon <模型目录> [conf] [iou]\n", argv[0], argv[0]);
        return 1;
    }
    std::string model_dir = argv[1];
    std::string img_path = argv[2];
    float conf_thres = argc > 3 ? atof(argv[3]) : 0.52f;
    float iou_thres = argc > 4 ? atof(argv[4]) : 0.45f;

    ncnn::Net net;
    net.opt.num_threads = 2;
    if (net.load_param((model_dir + "/best_ncnn.param").c_str()) != 0 ||
        net.load_model((model_dir + "/best_ncnn.bin").c_str()) != 0) {
        fprintf(stderr, "加载模型失败\n");
        return 1;
    }

    std::string json = infer_image(net, img_path, conf_thres, iou_thres);
    // 单次模式输出美化JSON
    printf("%s\n", json.c_str());
    return 0;
}

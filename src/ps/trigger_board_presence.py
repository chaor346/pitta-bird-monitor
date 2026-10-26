#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PYNQ-Z2 摄像头排查及按声音事件触发识别（Python 3.6）。
录像输出：视觉确认目标后持续录制，连续未检出满足条件才结束；随后转换H.264 MP4。
需要ffmpeg（带libx264）和ffprobe；只录图像，无音轨。
转换期间暂停下一轮事件处理；转换失败保留临时AVI及错误日志。
Ctrl+C取消转码并保留临时AVI；正常录像完成仍自动转MP4。
修复ncnn管道堵塞、无限等待和子进程退出回收；每10秒输出运行状态。
新增 --check-video：只检查MP4编码工具，不打开摄像头或加载模型。
新增 --camera-test：只采集并统计帧率，不启动模型/录像/网页视频。
新增 --snapshot-only：识别成功只保存对应输入帧的照片与JSON，避免视频编码。
修复 --detect-hz：仅在主线程提交时推理；WAITING不推理；最多一个在途任务。
结果与原始输入帧绑定，状态改变时丢弃上一事件结果；仅处理一次检测结果。
去掉720P自动回退、限制主循环空转，--snap不再加载模型。
保留原模型接口及ncnn可执行文件调用方式；没有将模型自动移到FPGA。
本文件实现声音触发图像识别与目标存在性持续录像。
示例：
  sudo python3 trigger_board.py --camera-test --width 640 --height 480 --fps 5
  sudo python3 trigger_board.py --mock --once --snapshot-only --detect-hz 0.5 --fps 5
"""
import argparse, json, os, subprocess, sys, tempfile, time, signal, shutil, math
import select
from av_recording_lock import RecordingLock
from collections import deque
# 给摄像头、音频与系统任务留CPU；ncnn若在C++中覆写线程数，仍需修改其源码。
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
import cv2
cv2.setNumThreads(1)
import numpy as np
import http.server
import threading

# ==================== MJPEG 网页视频流（低分辨率，省CPU） ====================
_stream_jpeg = None
_stream_lock = threading.Lock()

def set_stream_frame(frame):
    global _stream_jpeg
    small = cv2.resize(frame, (320, max(1, int(frame.shape[0] * 320 / frame.shape[1]))))
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 35])
    if ok:
        with _stream_lock:
            _stream_jpeg = buf.tobytes()

class _MjpegHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/stream"):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            self.connection.settimeout(2.0)
            while _running and not self.server.stopping.is_set():
                with _stream_lock:
                    jpg = _stream_jpeg
                if jpg is None:
                    time.sleep(0.05); continue
                try:
                    self.wfile.write(b"--frame\r\n")
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(jpg)))
                    self.end_headers()
                    self.wfile.write(jpg); self.wfile.write(b"\r\n")
                except OSError:
                    break
                time.sleep(0.08)
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, fmt, *args): pass

class _StreamServer(__import__("socketserver").ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def start_stream_server(port):
    srv = _StreamServer(("0.0.0.0", port), _MjpegHandler)
    srv.stopping = threading.Event()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

_running = True
_shutdown = threading.Event()
_INFER_TIMEOUT = 30.0
def _signal_handler(sig, frame):
    global _running
    _running = False
    _shutdown.set()
    print("\n收到停止信号，取消推理/转码，保留未完成录像的AVI，正在退出...", flush=True)
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

def _stop_process(proc):
    """只结束本程序创建的子进程；有界等待并回收。"""
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        except ProcessLookupError:
            pass


def _run_command(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30):
    """communicate持续排空管道，定期检查停止请求；子进程不读取终端。"""
    if _shutdown.is_set():
        raise RuntimeError('正在退出，取消子进程任务')
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout,
                            stderr=stderr, start_new_session=(os.name == 'posix'))
    deadline = time.monotonic() + timeout
    report = time.monotonic() + 5
    try:
        while True:
            if _shutdown.is_set():
                raise RuntimeError('用户停止了任务')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('子进程超时（%.0fs）：%s' % (timeout, command[0]))
            try:
                out, err = proc.communicate(timeout=min(0.2, remaining))
                return subprocess.CompletedProcess(command, proc.returncode, out, err)
            except subprocess.TimeoutExpired:
                if time.monotonic() >= report:
                    print('[WAIT] %s仍在处理，Ctrl+C可停止' % os.path.basename(command[0]), flush=True)
                    report = time.monotonic() + 5
    finally:
        _stop_process(proc)
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()


IS_LINUX = (os.name == "posix")
_CAM_BACKEND = cv2.CAP_V4L2 if IS_LINUX else cv2.CAP_ANY
def _fcc_str(v):
    return "".join([chr((int(v) >> 8 * i) & 0xFF) for i in range(4)])

def _make_capture(index):
    """兼容老版 OpenCV：新版支持 VideoCapture(index, backend)，
    老版（如 PYNQ 2.5 自带 OpenCV）只接受 1 个参数。"""
    try:
        return cv2.VideoCapture(index, _CAM_BACKEND)
    except TypeError:
        return cv2.VideoCapture(index)

def _safe_set(cap, prop, val):
    try:
        cap.set(prop, val)
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRIGGER_DIR = os.path.join(BASE_DIR, "runtime", "trigger")
TRIGGER_FILE = "pitta.trigger"
VIDEO_DIR = os.path.join(BASE_DIR, "runtime", "videos")
ANNO_DIR = os.path.join(BASE_DIR, "runtime", "annotated")
PREVIEW_DIR = os.path.join(BASE_DIR, "runtime", "preview")
INFER_BIN = os.path.join(BASE_DIR, "infer_ncnn")


# ==================== MJPG临时录像 -> H.264 MP4 ====================
# 录制阶段沿用原MJPG写入，结束后再转换，避免边识别边进行H.264编码。
# 本模块只录画面，不采集摄像头麦克风音轨。
def check_mp4_tools():
    ffmpeg = shutil.which('ffmpeg')
    ffprobe = shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        raise RuntimeError('MP4录像需要ffmpeg和ffprobe。请执行 sudo apt-get install ffmpeg')
    result = _run_command([ffmpeg, '-hide_banner', '-encoders'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=15)
    encoders = result.stdout.decode('utf-8', 'replace')
    if result.returncode != 0 or not any(
            len(line.split()) >= 2 and line.split()[1] == 'libx264'
            for line in encoders.splitlines()):
        raise RuntimeError('当前ffmpeg没有libx264编码器，请安装带libx264的ffmpeg版本。')
    return ffmpeg, ffprobe


class Mp4Recorder:
    """每个事件一个录像对象；release完成转码、验证，再公布最终MP4路径。

    暂存与失败文件保存在 videos/_work/；转换失败不会删除源AVI。
    release可重复调用，但只会转换一次；返回True表示已生成并验证MP4。
    """
    def __init__(self, output_path, fps, size, tools):
        self.output_path = os.path.abspath(output_path)
        if os.path.exists(self.output_path):
            raise RuntimeError('录像文件已存在，不覆盖：%s' % self.output_path)
        self.fps = float(fps)
        self.size = (int(size[0]), int(size[1]))
        self.ffmpeg, self.ffprobe = tools
        self.frame_count = 0
        self._closed = False
        self._success = False
        self.last_error = None
        self._writer = None
        work_dir = os.path.join(os.path.dirname(self.output_path), '_work')
        os.makedirs(work_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(output_path))[0]
        fd, self.avi_path = tempfile.mkstemp(prefix=stem + '_', suffix='.avi', dir=work_dir)
        os.close(fd)
        self.partial_path = self.avi_path[:-4] + '_encoding.mp4'
        self.log_path = self.avi_path[:-4] + '_convert.log'
        try:
            self._writer = cv2.VideoWriter(
                self.avi_path, cv2.VideoWriter_fourcc(*'MJPG'), self.fps, self.size)
            if not self._writer.isOpened():
                raise RuntimeError('无法创建MJPG临时录像编码器')
        except Exception:
            if self._writer is not None:
                self._writer.release()
            raise
        print('[VIDEO] 临时录制：%s' % self.avi_path)

    def write(self, frame):
        if self._closed:
            raise RuntimeError('录像已关闭')
        if (frame is None or frame.dtype != np.uint8 or frame.ndim != 3 or
                frame.shape[2] != 3 or
                (frame.shape[1], frame.shape[0]) != self.size):
            raise ValueError('录像帧必须是与摄像头尺寸一致的uint8 BGR三通道图像')
        self._writer.write(frame)
        self.frame_count += 1

    def release(self):
        if self._closed:
            return self._success
        self._closed = True
        stderr_text = ''
        try:
            self._writer.release()  # 先完成AVI索引，之后FFmpeg才读取它。
            if _shutdown.is_set():
                raise RuntimeError('用户停止，跳过MP4转码，保留已结束写入的AVI')
            if self.frame_count == 0:
                raise RuntimeError('没有写入有效帧，未生成MP4')
            timeout = max(120.0, self.frame_count / self.fps * 20.0)
            command = [
                self.ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                '-threads', '1', '-filter_threads', '1', '-i', self.avi_path,
                '-map', '0:v:0', '-an',
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                '-pix_fmt', 'yuv420p', '-threads', '1',
                '-movflags', '+faststart', self.partial_path
            ]
            print('[VIDEO] 录像结束，正在转换H.264 MP4；请等到“MP4保存完成”再复制文件。')
            result = _run_command(command, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, timeout=timeout)
            stderr_text = result.stderr.decode('utf-8', 'replace')
            if result.returncode != 0:
                raise RuntimeError('FFmpeg转换失败：%s' % stderr_text[-1500:])
            probe = _run_command([
                self.ffprobe, '-v', 'error', '-select_streams', 'v:0', '-count_frames',
                '-show_entries', 'stream=codec_name,pix_fmt,width,height,nb_read_frames:format=duration',
                '-of', 'json', self.partial_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            if probe.returncode != 0:
                raise RuntimeError('MP4校验失败：%s' % probe.stderr.decode('utf-8', 'replace')[-1000:])
            info = json.loads(probe.stdout.decode('utf-8'))
            streams = info.get('streams', [])
            if not streams:
                raise RuntimeError('MP4中没有视频轨道')
            video = streams[0]
            count = int(video.get('nb_read_frames', 0))
            duration = float(info.get('format', {}).get('duration', 0))
            if video.get('codec_name') != 'h264' or video.get('pix_fmt') != 'yuv420p':
                raise RuntimeError('MP4编码或像素格式与预期不一致')
            if count != self.frame_count or duration <= 0:
                raise RuntimeError('MP4帧数/时长异常：提交%d帧，解码得到%d帧，时长%.3fs'
                                   % (self.frame_count, count, duration))
            if os.path.exists(self.output_path):
                raise RuntimeError('目标文件已存在，不覆盖：%s' % self.output_path)
            os.replace(self.partial_path, self.output_path)
            self._success = True
            print('[VIDEO] MP4保存完成：%s (%d帧，%.2fs，H.264/yuv420p)'
                  % (self.output_path, count, duration))
        except Exception as error:
            self.last_error = str(error)
            print('[VIDEO] 未生成已验证的MP4：%s' % self.last_error)
            print('[VIDEO] 临时AVI已保留：%s' % self.avi_path)
            try:
                with open(self.log_path, 'w', encoding='utf-8') as log:
                    log.write(self.last_error + '\n' + stderr_text)
                print('[VIDEO] 转换日志：%s' % self.log_path)
            except OSError:
                pass
        if self._success:
            # 只有最终MP4验证并保存成功，才清理本次创建的中间文件。
            try:
                os.remove(self.avi_path)
            except OSError as error:
                print('[VIDEO] MP4已成功，但临时AVI清理失败：%s' % error)
        return self._success


# ==================== 独立抓帧线程：只保留最新一帧 ====================
class CameraThread:
    def __init__(self, index=0, width=640, height=480, fps=15,
                 prefer_mjpeg=True):
        self._idx = index
        self._want = (width, height, fps)
        self._lock = threading.Lock()
        self._latest = None
        self._fps = 0.0
        self._ok = False
        self._cap = None
        self._thread = None
        self._stop = threading.Event()
        self._seq = 0
        self._captured_at = 0.0
        # 不自动升到720P。所有属性都是请求，必须查看实际协商输出。
        modes = [(width, height, fps, "MJPG" if prefer_mjpeg else "YUYV")]
        for (w, h, f, fcc) in modes:
            if self._open(w, h, f, fcc):
                self._ok = True
                break
        if self._ok:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _open(self, w, h, fps, fcc):
        cap = _make_capture(self._idx)
        if not cap.isOpened():
            cap.release(); return False
        if fcc:
            _safe_set(cap, cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fcc))
        _safe_set(cap, cv2.CAP_PROP_FRAME_WIDTH, w)
        _safe_set(cap, cv2.CAP_PROP_FRAME_HEIGHT, h)
        _safe_set(cap, cv2.CAP_PROP_FPS, fps)
        _safe_set(cap, cv2.CAP_PROP_BUFFERSIZE, 1)
        for _ in range(8):
            cap.read()
        ok, f = cap.read()
        if not ok:
            cap.release(); return False
        try:
            afcc = _fcc_str(cap.get(cv2.CAP_PROP_FOURCC))
            aw, ah = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        except Exception:
            afcc, aw, ah = fcc or "?", f.shape[1], f.shape[0]
        self._cap = cap
        self.width, self.height = aw, ah
        self.fourcc = afcc
        print("[CAM] 请求 %dx%d @%s FPS %s" % (w, h, fps, fcc))
        print("[CAM] 实际 /dev/video%d: %dx%d 格式=%s 驱动报告FPS=%.2f"
              % (self._idx, aw, ah, afcc, cap.get(cv2.CAP_PROP_FPS)))
        if (aw, ah) != (w, h) or afcc != fcc:
            print("[CAM] 参数未完全生效，请用 v4l2-ctl --list-formats-ext 查看支持模式。")
        return True

    def _loop(self):
        last_t = time.time(); n = 0
        while _running and not self._stop.is_set():
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.01); continue
            with self._lock:
                self._latest = frame
                self._seq += 1
                self._captured_at = time.monotonic()
            n += 1
            now = time.time()
            if now - last_t >= 2.0:
                self._fps = n / (now - last_t); n = 0; last_t = now

    def read_packet(self, after_id=None):
        with self._lock:
            if self._latest is None or self._seq == after_id:
                return None
            return self._seq, self._captured_at, self._latest.copy()

    def read(self):
        packet = self.read_packet()
        return None if packet is None else packet[2]

    @property
    def measured_fps(self):
        return self._fps

    def release(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                print("[CAM] 驱动读取尚未返回，由进程退出释放设备，避免跨线程release崩溃。")
                return
        if self._cap is not None:
            self._cap.release()

    @property
    def ok(self):
        return self._ok


# ==================== 推理后端：优先进程内模型，否则 ncnn 子进程 ====================
# 若同目录有 vision_board.py（ONNX加载一次），优先用它，避免每帧重启进程、重载模型
_inproc = None
def _load_inproc(conf_thres):
    global _inproc
    if _inproc is not None:
        return _inproc
    onnx = os.path.join(BASE_DIR, "best.onnx")
    tfl = os.path.join(BASE_DIR, "best.tflite")
    try:
        from vision_board import BoardVision
        model = onnx if os.path.exists(onnx) else tfl
        if os.path.exists(model):
            _inproc = BoardVision(model, conf=conf_thres)
            print("[INFER] 使用进程内模型（只加载一次）: %s" % os.path.basename(model))
    except Exception as e:
        print("[INFER] 进程内模型不可用(%s)，改用 ncnn 子进程" % str(e)[:60])
        _inproc = False
    if _inproc is None:
        _inproc = False
        print("[INFER] 未发现可用进程内模型，使用ncnn子进程；每帧创建进程可能较慢。")
    return _inproc

# ==================== 常驻ncnn推理进程：模型只加载一次 ====================
_daemon = None
_daemon_lock = threading.Lock()

class _DaemonInfer:
    def __init__(self, model_dir, conf_thres):
        self._closed = threading.Event()
        self._close_lock = threading.Lock()
        self._errors = deque(maxlen=20)
        self._buffer = b''
        self.proc = subprocess.Popen(
            [INFER_BIN, "--daemon", model_dir, str(conf_thres)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, start_new_session=True)
        # 不等待stderr所谓的“就绪行”：有些版本根本不输出该行。
        # 持续排空stderr，避免ncnn写满管道后停止推理。
        self._reader = threading.Thread(target=self._drain_errors, daemon=True)
        self._reader.start()
        import fcntl
        for pipe in (self.proc.stdin, self.proc.stdout):
            fd = pipe.fileno()
            fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

    def _drain_errors(self):
        try:
            while True:
                chunk = self.proc.stderr.read(4096)
                if not chunk:
                    break
                self._errors.append(chunk.decode('utf-8', 'replace'))
        except (OSError, ValueError):
            pass

    def infer(self, img_path):
        deadline = time.monotonic() + _INFER_TIMEOUT
        pending = (img_path + '\n').encode('utf-8')
        while True:
            if self._closed.is_set() or _shutdown.is_set():
                raise RuntimeError('推理已取消')
            if time.monotonic() >= deadline:
                raise RuntimeError('ncnn等待结果超过%.0f秒' % _INFER_TIMEOUT)
            if self.proc.poll() is not None:
                raise RuntimeError('ncnn退出：' + ''.join(self._errors)[-500:])
            readers, writers, _ = select.select(
                [self.proc.stdout], [self.proc.stdin] if pending else [], [], 0.1)
            if writers:
                try:
                    pending = pending[os.write(self.proc.stdin.fileno(), pending):]
                except BlockingIOError:
                    pass
            if readers:
                try:
                    data = os.read(self.proc.stdout.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not data:
                    raise RuntimeError('ncnn输出已关闭')
                self._buffer += data
                if len(self._buffer) > 1024 * 1024:
                    raise RuntimeError('ncnn输出异常：单条结果超过1MB')
                if b'\n' in self._buffer:
                    line, self._buffer = self._buffer.split(b'\n', 1)
                    return json.loads(line.decode('utf-8'))

    def close(self):
        with self._close_lock:
            if self._closed.is_set():
                return
            self._closed.set()
            # 不往stdin写quit，避免与推理线程写同一管道或等待其锁。
            _stop_process(self.proc)
            self._reader.join(timeout=1)
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass


def _get_daemon(conf_thres):
    global _daemon
    with _daemon_lock:
        if _shutdown.is_set():
            return None
        if _daemon is None:
            try:
                _daemon = _DaemonInfer(BASE_DIR, conf_thres)
                print("[INFER] 常驻推理进程已启动(模型只加载一次)")
            except Exception as e:
                print("[INFER] 常驻进程启动失败(%s)，退化为单次子进程" % str(e)[:60])
                _daemon = False
        return _daemon if _daemon else None


def infer_once(frame, conf_thres):
    """识别一帧，返回 boxes 列表，每个 {'box':[x1,y1,x2,y2],'cls':..,'conf':..}。"""
    if _shutdown.is_set():
        raise RuntimeError('正在退出')
    model = _load_inproc(conf_thres)
    if model:
        dets, _ = model.detect(frame)
        boxes = []
        for d in dets:
            x1, y1, x2, y2, c, cid = d
            if c >= conf_thres:
                boxes.append({"box": [float(x1), float(y1), float(x2), float(y2)],
                              "cls": "pitta", "conf": float(c)})
        return boxes
    # 写临时图
    tmp_img = os.path.join(tempfile.gettempdir(), "pitta_frame_%d.jpg" % os.getpid())
    if not cv2.imwrite(tmp_img, frame, [cv2.IMWRITE_JPEG_QUALITY, 80]):
        raise RuntimeError("无法写入ncnn临时输入图像")
    # 优先用常驻进程
    daemon = _get_daemon(conf_thres)
    if daemon:
        try:
            result = daemon.infer(tmp_img)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result.get("boxes", [])
        except Exception as e:
            daemon.close()
            global _daemon
            with _daemon_lock:
                _daemon = False
            if _shutdown.is_set():
                raise RuntimeError('推理已取消')
            print("[INFER] 常驻进程异常(%s)，已清理，尝试单次子进程" % str(e)[:120])
    # 兜底：单次子进程
    try:
        ret = _run_command([INFER_BIN, BASE_DIR, tmp_img, str(conf_thres)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if ret.returncode != 0:
            raise RuntimeError("ncnn返回%d: %s" %
                               (ret.returncode, ret.stderr.decode("utf-8", "ignore")[-300:]))
        result = json.loads(ret.stdout.decode("utf-8", "ignore"))
        return result.get("boxes", [])
    except Exception as error:
        raise RuntimeError("ncnn识别失败: %s" % error)


# ==================== 异步推理线程：识别慢也不阻塞画面/录像 ====================
class InferenceWorker(threading.Thread):
    def __init__(self, cam, conf_thres):
        super().__init__(daemon=True)
        self.cam, self.conf = cam, conf_thres
        self._cond = threading.Condition()
        self._pending = None
        self._result = None
        self._busy = False
        self._stopped = False
        self._epoch = 0
        self._last_seq = -1

    def submit(self, frame_id=None):
        with self._cond:
            if self._stopped or self._busy or self._pending is not None or self._result is not None:
                return False
            packet = self.cam.read_packet(after_id=self._last_seq)
            if packet is None:
                return False
            self._last_seq = packet[0]
            self._pending = (self._epoch, packet)
            self._cond.notify()
            return True

    def reset(self):
        # 在途推理不强杀；完成后因epoch不同而被丢弃，不用于新事件。
        with self._cond:
            self._epoch += 1
            self._pending = None
            self._result = None
            self._last_seq = -1

    def take_result(self):
        with self._cond:
            result = self._result
            self._result = None
            return result

    def close(self):
        with self._cond:
            self._stopped = True
            self._pending = None
            self._cond.notify_all()

    def run(self):
        while _running:
            with self._cond:
                while self._pending is None and not self._stopped and _running:
                    self._cond.wait(timeout=0.2)
                if self._stopped or not _running:
                    return
                epoch, packet = self._pending
                self._pending = None
                self._busy = True
            seq, captured_at, frame = packet
            started = time.monotonic()
            error = None
            try:
                boxes = infer_once(frame, self.conf)
            except Exception as exc:
                boxes, error = [], str(exc)
            result = dict(seq=seq, captured_at=captured_at, frame=frame,
                          boxes=boxes, error=error,
                          latency=time.monotonic()-started)
            with self._cond:
                self._busy = False
                if epoch == self._epoch and not self._stopped:
                    self._result = result


def camera_test(cam, seconds):
    print("[TEST] 纯采集测试：不加载模型、不编码视频、不启动网页流。")
    started = last_report = time.monotonic()
    previous_seq = first_seq = None
    first_time = last_time = None
    while _running and time.monotonic() - started < seconds:
        packet = cam.read_packet(after_id=previous_seq)
        if packet is not None:
            previous_seq, last_time, frame = packet
            if first_seq is None:
                first_seq, first_time = previous_seq, last_time
        now = time.monotonic()
        if now-last_report >= 2.0:
            age = -1 if last_time is None else now-last_time
            print("[TEST] 采集线程FPS=%.2f 最新帧距今=%.3fs" % (cam.measured_fps, age))
            last_report = now
        time.sleep(0.01)
    if first_time is not None and last_time > first_time:
        print("[TEST] 平均采集FPS=%.2f，实际尺寸=%dx%d，格式=%s" %
              ((previous_seq-first_seq)/(last_time-first_time),cam.width,cam.height,cam.fourcc))
    else:
        print("[TEST] 未得到足够的有效帧，检查设备、格式、USB连接及供电。")
    print("[TEST] 此FPS包含OpenCV取帧/解码，不包含模型推理，也不等于传感器唯一曝光数。")





def draw_boxes(frame, boxes):
    vis = frame.copy()
    for b in boxes:
        x1, y1, x2, y2 = [int(v) for v in b["box"]]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(vis, "%s %.2f" % (b.get("cls", "pitta"), b["conf"]),
                    (x1, max(0, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 255, 0), 1)
    return vis


class AbsenceGate:
    """Measure absence using input-frame capture times, not delayed result times."""
    def __init__(self, hits, seconds):
        self.hits, self.seconds = hits, seconds
        self.reset()

    def reset(self):
        self.misses = 0
        self.first_miss = None
        self.span = 0.0

    def update(self, bird_present, captured_at):
        if bird_present:
            self.reset()
            return False
        if self.first_miss is None:
            self.first_miss = captured_at
        self.misses += 1
        self.span = max(0.0, captured_at - self.first_miss)
        return self.misses >= self.hits and self.span >= self.seconds


def main():
    global _INFER_TIMEOUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", type=float, default=0.52)
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--no-mjpeg", action="store_true", help="请求YUYV格式作对照；以实际协商结果为准")
    ap.add_argument('--record-sec', type=float, default=None,
                    help='Compatibility only; ignored in presence-based recording')
    ap.add_argument('--absence-hits', type=int, default=3,
                    help='Consecutive valid no-bird results required to stop')
    ap.add_argument('--absence-sec', type=float, default=6.0,
                    help='Minimum span between first and last no-bird input frames')
    ap.add_argument('--vision-timeout', type=float, default=60.0,
                    help='Fault stop if no fresh successful visual result for this long')
    ap.add_argument("--cooldown", type=float, default=5.0)
    ap.add_argument("--detect-hz", type=float, default=2.0,
                    help="搜索时每秒最多识别几次(板子慢建议1-3)")
    ap.add_argument("--record-fps", type=int, default=8)
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--stream-port", type=int, default=8080)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--search-sec", type=float, default=15.0)
    ap.add_argument("--snap", action="store_true")
    ap.add_argument("--camera-test", action="store_true", help="不启动模型的纯采集测试")
    ap.add_argument("--test-seconds", type=float, default=20.0)
    ap.add_argument("--snapshot-only", action="store_true", help="检测成功只存照片和JSON，不编码录像")
    ap.add_argument("--check-video", action="store_true", help="仅检查FFmpeg/H.264工具，不使用摄像头")
    ap.add_argument('--infer-timeout', type=float, default=30.0, help='ncnn每次请求超时秒数（含首帧加载）')
    ap.add_argument('--audio-pause-file', default=os.path.join(TRIGGER_DIR, 'vision_recording.lock'))
    args = ap.parse_args()
    if not math.isfinite(args.infer_timeout) or args.infer_timeout <= 0:
        ap.error('infer-timeout必须是正有限数')
    _INFER_TIMEOUT = args.infer_timeout
    if args.fps <= 0 or args.detect_hz <= 0 or args.test_seconds <= 0:
        ap.error("fps、detect-hz、test-seconds必须大于0")
    if args.record_fps <= 0 or args.absence_hits < 1:
        ap.error('record-fps and absence-hits must be positive')
    if not math.isfinite(args.absence_sec) or args.absence_sec < 0:
        ap.error('absence-sec must be finite and nonnegative')
    if not math.isfinite(args.vision_timeout) or args.vision_timeout <= args.absence_sec:
        ap.error('vision-timeout must be finite and greater than absence-sec')
    if args.record_sec is not None:
        print('[VIDEO] --record-sec ignored: recording ends after confirmed absence.', flush=True)
    if args.check_video:
        try:
            ffmpeg, ffprobe = check_mp4_tools()
            print("[VIDEO] 工具检查通过：ffmpeg含libx264，ffprobe可用。")
            print("[VIDEO] ffmpeg：%s" % ffmpeg)
            print("[VIDEO] ffprobe：%s" % ffprobe)
        except Exception as error:
            ap.error(str(error))
        return
    video_tools = None
    if not (args.camera_test or args.snap or args.snapshot_only):
        try:
            video_tools = check_mp4_tools()
        except Exception as error:
            ap.error(str(error))

    for d in [TRIGGER_DIR, VIDEO_DIR, ANNO_DIR]:
        os.makedirs(d, exist_ok=True)

    cam = CameraThread(args.camera, args.width, args.height, args.fps,
                       prefer_mjpeg=not args.no_mjpeg)
    if not cam.ok:
        print("无法打开摄像头 /dev/video%d" % args.camera)
        sys.exit(1)

    # 诊断分支必须在创建推理线程之前执行。
    if args.camera_test or args.snap:
        try:
            if args.camera_test:
                camera_test(cam, args.test_seconds)
            else:
                deadline = time.monotonic() + 5.0
                frame = None
                while _running and time.monotonic() < deadline:
                    frame = cam.read()
                    if frame is not None:
                        break
                    time.sleep(0.05)
                if frame is None:
                    raise RuntimeError("5秒内没有读到图像")
                path = os.path.join(BASE_DIR, "runtime", "snap.jpg")
                if not cv2.imwrite(path, frame):
                    raise RuntimeError("照片写入失败")
                print("拍照完成：%s (%dx%d)" % (path, frame.shape[1], frame.shape[0]))
        finally:
            cam.release()
        return

    worker = InferenceWorker(cam, args.conf)
    worker.start()
    stream_server = None
    if args.stream:
        try:
            stream_server = start_stream_server(args.stream_port)
        except Exception:
            worker.close()
            worker.join(timeout=1)
            cam.release()
            raise
        print("实时视频流：http://<板子实际IP>:%d/" % args.stream_port)

    print("等待事件提交后才启动识别；耗时以每次[INFER]日志为准。")
    state = "SEARCHING" if args.mock else "WAITING"
    search_start = time.time()
    recording = False
    record_frames = 0
    absence = AbsenceGate(args.absence_hits, args.absence_sec)
    next_record_at = 0.0
    record_started = 0.0
    last_valid_at = 0.0
    stop_reason = None
    writer = None; video_name = ""; last_record_time = 0
    last_detect_t = 0; last_boxes = []; tick = 0
    last_cam_seq = None
    last_stream_t = 0.0
    status_at = time.monotonic()
    print("[RUN] 程序正在前台运行；Ctrl+C退出。--once在首次成功保存后退出。", flush=True)

    recording_lock = RecordingLock(args.audio_pause_file)
    print('[AV] Recording lock: ' + recording_lock.path, flush=True)

    def check_trigger():
        tp = os.path.join(TRIGGER_DIR, TRIGGER_FILE)
        if os.path.exists(tp):
            try: os.remove(tp)
            except Exception: pass
            return True
        return False

    try:
        while _running:
            # 不忙等、不重复复制/处理同一已取得帧。
            time.sleep(0.01)
            if time.monotonic() - status_at >= 10:
                print('[STATUS] %s；采集%.1f FPS；Ctrl+C退出' % (state, cam.measured_fps), flush=True)
                status_at = time.monotonic()
            packet = cam.read_packet(after_id=last_cam_seq)
            if packet is None:
                if state == 'RECORDING' and time.monotonic() - last_valid_at >= args.vision_timeout:
                    raise RuntimeError('No frames/results during recording; preserving temporary AVI; not classified as bird departure')
                continue
            last_cam_seq, captured_at, frame = packet
            tick += 1
            if args.stream and time.monotonic() - last_stream_t >= 0.5:
                set_stream_frame(frame)
                last_stream_t = time.monotonic()

            if state == "WAITING":
                if check_trigger():
                    worker.reset()
                    last_detect_t = 0
                    state = "SEARCHING"; search_start = time.time()
                    print(">>> 收到声音触发，开始搜鸟(%.0fs窗口)" % args.search_sec)
                else:
                    time.sleep(0.02)
                continue

            if state == "SEARCHING":
                if time.time() - search_start >= args.search_sec:
                    print("  搜索超时，未检测到鸟，回到等待")
                    worker.reset()
                    state = "WAITING" if not args.mock else "SEARCHING"
                    if args.mock: search_start = time.time()
                    continue
                # 按 detect-hz 节流提交识别（异步，不阻塞）
                now = time.time()
                if now - last_detect_t >= 1.0 / args.detect_hz:
                    if worker.submit(tick):
                        last_detect_t = now
                result = worker.take_result()
                if result is None:
                    continue
                if result["error"]:
                    print("[INFER] 错误：%s" % result["error"])
                    continue
                print("[INFER] 帧%d 推理%.3fs，采集FPS=%.2f，结果帧距今%.3fs" %
                      (result["seq"], result["latency"], cam.measured_fps,
                       time.monotonic()-result["captured_at"]))
                boxes = result["boxes"]
                if boxes:
                    conf = max(b["conf"] for b in boxes)
                    print("[检测] 发现仙八色鸫! conf=%.2f 框数=%d (单帧耗时%.1fs)"
                          % (conf, len(boxes), result["latency"]))
                    if time.time() - last_record_time < args.cooldown:
                        continue
                    ts = int(time.time() * 1000)
                    # 必须给推理输入帧画框，不能把旧框画在当前新画面上。
                    snapshot = os.path.join(ANNO_DIR, "frame_%d.jpg" % ts)
                    if not cv2.imwrite(snapshot, draw_boxes(result["frame"], boxes)):
                        raise RuntimeError("无法保存检测照片")
                    with open(os.path.join(ANNO_DIR, "frame_%d.json" % ts), "w") as log:
                        json.dump(dict(saved_at=time.time(), frame_seq=result["seq"],
                                       inference_seconds=result["latency"], boxes=boxes), log)
                    worker.reset()
                    if args.snapshot_only:
                        print(">>> 已保存检测照片和事件JSON：%s" % snapshot)
                        last_record_time = time.time()
                        if args.once:
                            break
                        state = "WAITING" if not args.mock else "SEARCHING"
                        if args.mock:
                            search_start = time.time()
                        continue
                    video_name = "pitta_%d.mp4" % ts
                    recording_lock.begin()
                    print('[AV] Audio prediction paused during recording/conversion.', flush=True)
                    writer = Mp4Recorder(
                        os.path.join(VIDEO_DIR, video_name), args.record_fps,
                        (cam.width, cam.height), video_tools)
                    state = "RECORDING"; recording = True; record_frames = 0
                    absence.reset()
                    record_started = last_valid_at = time.monotonic()
                    next_record_at = record_started
                    last_detect_t = 0
                    stop_reason = None
                    last_boxes = boxes; last_record_time = time.time()
                    print(">>> 开始录像: %s" % video_name)
                continue

            if state == "RECORDING":
                now_mono = time.monotonic()
                # Video frames continue independently of the slower inference worker.
                if now_mono >= next_record_at:
                    writer.write(frame)
                    record_frames += 1
                    next_record_at += 1.0 / args.record_fps
                    if next_record_at < now_mono:
                        next_record_at = now_mono + 1.0 / args.record_fps
                if now_mono - last_detect_t >= 1.0 / args.detect_hz:
                    if worker.submit(tick):
                        last_detect_t = now_mono
                result = worker.take_result()
                if result is not None:
                    result_age = time.monotonic() - result['captured_at']
                    if result['error'] or result_age > args.vision_timeout:
                        absence.reset()  # Error/unknown is not proof of absence.
                        print('[RECORD-INFER] Error/stale result: %s' %
                              (result['error'] or 'input frame too old'), flush=True)
                    else:
                        last_valid_at = result['captured_at']
                        absent = absence.update(bool(result['boxes']), result['captured_at'])
                        print('[RECORD-INFER] bird=%s misses=%d span=%.2fs infer=%.2fs' %
                              (bool(result['boxes']), absence.misses, absence.span,
                               result['latency']), flush=True)
                        if absent:
                            stop_reason = 'confirmed_absence'
                if time.monotonic() - last_valid_at >= args.vision_timeout:
                    stop_reason = 'vision_timeout'
                if stop_reason:
                    elapsed_record = time.monotonic() - record_started
                    worker.reset()  # Ignore any in-flight result belonging to this recording.
                    print('[VIDEO] Stop: %s; recorded wall time %.2fs' %
                          (stop_reason, elapsed_record), flush=True)
                    saved = writer.release()  # Lock stays held throughout MP4 conversion.
                    error = writer.last_error
                    writer = None; recording = False
                    with open(os.path.join(VIDEO_DIR, video_name + '.json'), 'w') as log:
                        json.dump(dict(video=video_name, saved=saved, error=error,
                                       stop_reason=stop_reason, recording_wall_seconds=elapsed_record,
                                       frames=record_frames, configured_fps=args.record_fps,
                                       encoded_seconds=record_frames / float(args.record_fps),
                                       absence_hits=args.absence_hits, absence_sec=args.absence_sec),
                                  log, indent=2)
                    recording_lock.end()
                    print('[AV] Recording/conversion finished; audio may resume.', flush=True)
                    if not saved:
                        raise RuntimeError('MP4 conversion failed; temporary AVI retained. %s' % error)
                    print('>>> 录像保存: %s (%d帧)' % (video_name, record_frames))
                    last_record_time = time.time()
                    last_boxes = []
                    if args.once:
                        break
                    state = 'WAITING' if not args.mock else 'SEARCHING'
                    if args.mock:
                        search_start = time.time()
                continue
    except KeyboardInterrupt:
        print("\n正在停止...")
    finally:
        recording_lock.close()
        print('[EXIT] 正在清理子进程、摄像头和录像...', flush=True)
        _shutdown.set()
        worker.close()
        with _daemon_lock:
            daemon_to_close = _daemon
        if daemon_to_close:
            daemon_to_close.close()
        worker.join(timeout=3.0)
        if worker.is_alive():
            print('[EXIT] 推理线程尚未返回（可能为进程内模型）；不再无限等待。')
        cam.release()
        if stream_server is not None:
            stream_server.stopping.set()
            stream_server.shutdown()
            stream_server.server_close()
        if writer is not None:
            writer.release()
        try:
            os.remove(os.path.join(tempfile.gettempdir(), 'pitta_frame_%d.jpg' % os.getpid()))
        except OSError:
            pass
        print("已停止，照片/事件: %s，录像: %s" % (ANNO_DIR, VIDEO_DIR))

if __name__ == "__main__":
    main()

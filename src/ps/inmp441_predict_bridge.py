#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python 3.6+. Requires user's audio_numpy.py/audio_model.npz.
Keeps the tested inmp441_record.py DMA implementation unchanged.
Diagnostic streaming: repeated DMA reset is NOT proven gapless.
"""
import os
# Limit BLAS contention before importing numpy.
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import argparse
import csv
import json
import queue
import threading
import time
import wave
import tempfile
import uuid
import numpy as np

FS = 32000
WINDOW = 64000


def decode_right24(words):
    u = np.asarray(words, dtype=np.int32).astype(np.int64) & 0xffffff
    signed = np.where(u & 0x800000, u - 0x1000000, u)
    # Same PCM16 conversion as the tested recorder; WAV replay matches live input.
    pcm = np.clip(np.rint(signed.astype(np.float64) / 256.0),
                  -32768, 32767).astype('<i2')
    return pcm


def wav_windows(path, hop, channel):
    with wave.open(path, 'rb') as w:
        if w.getframerate() != FS or w.getsampwidth() != 2:
            raise ValueError('WAV must be PCM16, 32000 Hz. No implicit resampling.')
        channels = w.getnchannels()
        if channel >= channels:
            raise ValueError('Requested channel is absent in WAV')
        x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2')
        x = x.reshape(-1, channels)[:, channel].astype(np.float32) / 32768.0
    if len(x) < WINDOW:
        raise ValueError('WAV must contain at least 2 seconds')
    for start in range(0, len(x) - WINDOW + 1, hop):
        yield start, x[start:start + WINDOW].copy(), None
    # Final incomplete window deliberately omitted, not silently zero-padded.


class Capture(threading.Thread):
    def __init__(self, args, jobs, stop, done, mmio, buf, driver):
        threading.Thread.__init__(self)
        self.args, self.jobs, self.stop, self.done = args, jobs, stop, done
        # PYNQ 资源（Overlay/MMIO/连续缓冲）必须在主线程创建，再传给本线程；
        # 因为 pynq.xlnk 在导入时会 signal.signal(SIGSEGV)，只能在主线程执行。
        self.mmio, self.buf, self.driver = mmio, buf, driver
        self.error = None
        self.stats = {'packets': 0, 'short_packets': 0, 'samples': 0}

    def run(self):
        mmio, buf, driver = self.mmio, self.buf, self.driver
        wav = None
        start_time = time.monotonic()
        try:
            wav = wave.open(os.path.join(self.args.out, 'microphone.wav'), 'wb')
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(FS)
            pending = np.empty(0, np.float32)
            sample_start = 0
            hop = int(round(self.args.hop * FS))
            start_time = time.monotonic()
            print('[MIC] Listening; saved WAV time is received-sample time.', flush=True)
            while not self.stop.is_set() and time.monotonic() - start_time < self.args.seconds:
                count = driver.recv_packet(mmio, buf, driver.PKT_BEATS * 4)
                if count <= 0 or count > driver.PKT_BEATS * 4 or count % 8:
                    raise RuntimeError('Invalid packet bytes=%d; stereo alignment unsafe' % count)
                buf.invalidate()
                raw = buf[:count // 4].copy().reshape(-1, 2)
                self.stats['packets'] += 1
                if count != driver.PKT_BEATS * 4:
                    self.stats['short_packets'] += 1
                # ========== 双通道择优新增代码 ==========
                pcm_ch0 = decode_right24(raw[:, 0])
                pcm_ch1 = decode_right24(raw[:, 1])
                rms_ch0 = np.sqrt(np.mean(pcm_ch0.astype(np.float64)**2))
                rms_ch1 = np.sqrt(np.mean(pcm_ch1.astype(np.float64)**2))
                if rms_ch0 >= rms_ch1:
                    pcm = pcm_ch0
                else:
                    pcm = pcm_ch1
                # ========================================

                wav.writeframesraw(pcm.tobytes())
                self.stats['samples'] += len(pcm)
                pending = np.concatenate((pending, pcm.astype(np.float32) / 32768.0))
                while len(pending) >= WINDOW:
                    job = (sample_start, pending[:WINDOW].copy(), time.monotonic())
                    try:
                        self.jobs.put_nowait(job)
                    except queue.Full:
                        raise RuntimeError('Inference queue full: cannot maintain requested hop. '
                                           'Stopped rather than silently dropping audio windows.')
                    pending = pending[hop:]
                    sample_start += hop
        except BaseException as e:
            self.error = '%s: %s' % (type(e).__name__, e)
        finally:
            self.stats['wall_seconds'] = time.monotonic() - start_time
            self.stats['audio_seconds'] = self.stats['samples'] / float(FS)
            self.stats['error'] = self.error
            if mmio is not None:
                try:
                    driver.reset_dma(mmio)
                except Exception:
                    pass
            if buf is not None:
                buf.freebuffer()
            if wav is not None:
                wav.close()
            self.done.set()



def publish_vision_trigger(path, event):
    """Legacy trigger_board interface. One pending event; no completion ACK.
    Atomic hard-link publication prevents partial reads and pending overwrite.
    Use a local Linux filesystem, not a Windows shared folder.
    """
    directory = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix='.pitta-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(event, f)
            f.flush()
        try:
            os.link(temporary, path)
            return 'published'
        except FileExistsError:
            return 'pending_exists_coalesced'
    finally:
        os.unlink(temporary)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', default='audio_model.npz')
    ap.add_argument('--wav', help='Offline PCM16 32000 Hz WAV; omit for INMP441')
    ap.add_argument('--overlay', default='inmp441.bit')
    ap.add_argument('--dma-name', default='axi_dma_0')
    ap.add_argument('--channel', type=int, choices=[0, 1], default=0,
                    help='0=left slot, 1=right slot; mono WAV requires 0')
    ap.add_argument('--seconds', type=float, default=60.0, help='Live wall-clock duration')
    ap.add_argument('--hop', type=float, default=0.5)
    ap.add_argument('--threshold', type=float, required=True,
                    help='Use your validated threshold; 0.5 only for initial functional test')
    ap.add_argument('--min-hits', type=int, default=2)
    ap.add_argument('--cooldown', type=float, default=30.0)
    ap.add_argument('--out', required=True, help='New output directory (must not exist)')
    ap.add_argument('--vision-trigger', default=None,
                    help='Absolute path to visual script runtime/trigger/pitta.trigger')
    ap.add_argument('--trigger-from-wav', action='store_true',
                    help='Explicitly permit offline WAV to trigger physical camera')
    args = ap.parse_args()
    if args.vision_trigger:
        if not os.path.isabs(args.vision_trigger):
            ap.error('--vision-trigger requires an absolute path')
        if args.wav and not args.trigger_from_wav:
            ap.error('Offline WAV triggering requires --trigger-from-wav')
        trigger_dir = os.path.dirname(args.vision_trigger)
        if not os.path.isdir(trigger_dir):
            ap.error('Trigger directory absent. Start visual program first and check its path.')
        if not os.access(trigger_dir, os.W_OK):
            ap.error('Trigger directory is not writable')
        print('[BRIDGE] Target: ' + args.vision_trigger, flush=True)
        if os.path.exists(args.vision_trigger):
            print('[BRIDGE] Existing pending trigger retained; visual program must consume it.', flush=True)

    if not (0 < args.hop <= 2 and args.seconds > 0 and
            0 <= args.threshold <= 1 and args.min_hits >= 1 and args.cooldown >= 0):
        ap.error('Invalid duration/hop/threshold/min-hits/cooldown')
    if round(args.hop * FS) < 1:
        ap.error('hop is smaller than one sample')
    from audio_numpy import NumpyBirdCNN
    with np.load(args.model, allow_pickle=False) as pack:
        if int(pack['sr']) != FS:
            raise ValueError('Model sample rate is not 32000 Hz')
    model = NumpyBirdCNN(args.model)
    t = time.monotonic()
    warm = float(model.predict(np.zeros(WINDOW, np.float32)))
    if not np.isfinite(warm) or not 0 <= warm <= 1:
        raise ValueError('predict() must return a finite target probability')
    print('[MODEL] Warm-up %.3fs; input 32000 Hz / 2s' % (time.monotonic() - t))
    if os.path.exists(args.out):
        ap.error('Output directory already exists; choose a new --out. Nothing deleted.')
    os.makedirs(args.out)
    with open(os.path.join(args.out, 'config.json'), 'w') as f:
        json.dump(vars(args), f, indent=2)
    stop, done = threading.Event(), threading.Event()
    jobs = queue.Queue(maxsize=4)
    cap = None
    mmio = buf = driver = None
    hits, last_trigger = 0, -float('inf')
    timings = []
    if args.wav:
        windows = iter(wav_windows(args.wav, int(round(args.hop * FS)), args.channel))
    else:
        # 以下 pynq 导入/Overlay/分配必须在主线程执行（pynq.xlnk 导入时会注册 SIGSEGV）
        from pynq import Overlay, allocate, MMIO
        from pynq.ps import Clocks
        import inmp441_record as driver
        if driver.FS != FS or driver.BEATS_PER_FRAME != 2:
            raise ValueError('Recorder format differs from expected stereo 32000 Hz')
        ol = Overlay(os.path.abspath(args.overlay))
        info = ol.ip_dict[args.dma_name]
        mmio = MMIO(info['phys_addr'], info['addr_range'])
        Clocks.fclk0_mhz = 100.0
        time.sleep(0.1)
        if abs(Clocks.fclk0_mhz - 100.0) > 0.1:
            raise RuntimeError('FCLK0 could not be set to 100 MHz')
        buf = allocate(shape=(driver.PKT_BEATS,), dtype=np.int32)
        print('[OVERLAY] %s 已加载；FCLK0=%.1f MHz；DMA=%s' %
              (args.overlay, Clocks.fclk0_mhz, args.dma_name), flush=True)
        cap = Capture(args, jobs, stop, done, mmio, buf, driver)
    try:
        with open(os.path.join(args.out, 'scores.csv'), 'w', newline='') as f, \
                open(os.path.join(args.out, 'events.jsonl'), 'w') as ef:
            writer = csv.writer(f)
            writer.writerow(['start_s', 'end_s', 'score', 'rms_dbfs', 'infer_s',
                             'window_ready_to_result_s', 'trigger', 'unix_time'])
            if cap is not None:
                cap.start()
            while True:
                if cap is None:
                    try:
                        sample_start, y, ready = next(windows)
                    except StopIteration:
                        break
                else:
                    if done.is_set() and jobs.empty():
                        break
                    try:
                        sample_start, y, ready = jobs.get(timeout=0.2)
                    except queue.Empty:
                        continue
                t = time.monotonic()
                score = float(model.predict(np.ascontiguousarray(y, dtype=np.float32)))
                elapsed = time.monotonic() - t
                if not np.isfinite(score) or not 0 <= score <= 1:
                    raise ValueError('Invalid model probability')
                timings.append(elapsed)
                start, end = sample_start / float(FS), (sample_start + WINDOW) / float(FS)
                rms = 20 * np.log10(max(float(np.sqrt(np.mean(y.astype(np.float64)**2))), 1e-12))
                hits = hits + 1 if score >= args.threshold else 0
                trigger = hits >= args.min_hits and end - last_trigger >= args.cooldown
                age = '' if ready is None else time.monotonic() - ready
                wall = time.time()
                if trigger:
                    last_trigger, hits = end, 0
                    event = dict(start_s=start, end_s=end, score=score, unix_time=wall,
                                 event_id=uuid.uuid4().hex,
                                 source='inmp441' if cap is not None else 'wav',
                                 audio_output=os.path.abspath(args.out),
                                 note='window evidence, not exact call onset/offset')
                    if args.vision_trigger:
                        try:
                            status = publish_vision_trigger(args.vision_trigger, event)
                        except OSError as exc:
                            status = 'publish_failed'
                            event['vision_error'] = str(exc)
                        event['vision_notify'] = status
                        event['vision_trigger_path'] = args.vision_trigger
                        print('[BRIDGE] %s event=%s' % (status, event['event_id']), flush=True)
                    else:
                        event['vision_notify'] = 'disabled'
                    ef.write(json.dumps(event) + '\n')
                    ef.flush()
                writer.writerow([start, end, score, rms, elapsed, age, int(trigger), wall])
                f.flush()
                print('[AUDIO] %.2f~%.2fs score=%.4f rms=%.1fdBFS infer=%.3fs%s' %
                      (start, end, score, rms, elapsed, ' TRIGGER' if trigger else ''), flush=True)
    except KeyboardInterrupt:
        print('\nStopping capture...')
    finally:
        stop.set()
        if cap is not None and cap.ident is not None:
            cap.join()  # Driver polling has timeout; do not free DMA buffer from main thread.
        summary = dict(capture=cap.stats if cap else None, windows=len(timings),
                       mean_infer_s=float(np.mean(timings)) if timings else None,
                       max_infer_s=max(timings) if timings else None,
                       gapless_verified=False if cap else None)
        with open(os.path.join(args.out, 'summary.json'), 'w') as f:
            json.dump(summary, f, indent=2)
        print('[SAVE] ' + os.path.abspath(args.out))
    if cap is not None and cap.error:
        raise RuntimeError(cap.error)
    if timings and np.mean(timings) >= args.hop:
        print('[WARN] Mean inference >= hop; real-time backlog likely.')


if __name__ == '__main__':
    main()

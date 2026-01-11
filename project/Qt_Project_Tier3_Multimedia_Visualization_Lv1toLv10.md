# Tier 3｜多媒體 + 可視化（Camera / RTSP / 錄影 / OpenCV / 即時曲線）專案教學.md
> 接續 Tier 2：你已經把 **工控 I/O + 協議解析 + 重連 + Replay** 做成穩定框架  
> Tier 3 目標：把上位機做成「現場真的會用」：**畫面監看 + 錄影 + 影像處理 + 即時曲線**，而且依然不卡 UI  
> 覆蓋重點：**Lv8 加深**（但仍沿用 Lv1～Lv7 / Lv9～Lv10 的平台骨架）

---

## 0) Tier 3 你會做到什麼（工程驗收清單）
### ✅ 多媒體（畫面）
- USB Camera（OpenCV 或 Qt Multimedia）
- RTSP（推薦：GStreamer / FFmpeg pipeline，Qt 只做 UI 管理）
- 畫面顯示不卡（UI 15~30fps 可控）
- 影像處理 pipeline（5fps 或自訂節流，丟幀策略）

### ✅ 錄影（可落地）
- 顯示與錄影分離（Display pipeline ≠ Record pipeline）
- 最小版：每秒存圖 / 或 OpenCV VideoWriter 寫 mp4/avi（依平台/codec 而定）
- 錄影資料與事件對齊（timestamp）

### ✅ 可視化（曲線/狀態）
- 即時曲線（QtCharts 或 pyqtgraph 擇一）
- UI 批次刷新（100ms）避免刷爆
- 指標顯示：FPS、丟幀數、延遲、queue 長度

### ✅ Replay 延伸（Tier3 版）
- replay.jsonl 記錄：state/raw/parsed + camera timestamp（可選）
- 回放時能「同時」重播：控制事件 + 曲線（影像可用檔案方式回放）

---

# 1) Tier 3 建議的專案結構（在 Tier2 上新增）
```
qt_control_desk/
├─ core/
│  ├─ multimedia/
│  │  ├─ camera_base.py          ✅（統一介面：start/stop + frame signal）
│  │  ├─ camera_opencv.py        ✅（USB camera：cv2.VideoCapture）
│  │  ├─ recorder_opencv.py      ✅（錄影：cv2.VideoWriter / 存圖）
│  │  └─ frame_convert.py        ✅（cv→QImage 工具）
│  ├─ plot/
│  │  ├─ plot_buffer.py          ✅（ring buffer + 節流）
│  │  └─ plot_widget_stub.py     ✅（先用 stub，或接 pyqtgraph/QtCharts）
│  └─ metrics_video.py           ✅（影像 fps/丟幀/延遲）
└─ ui/
   ├─ main_window.py             🔁（加入 CameraTab / PlotTab）
   └─ tabs/
      ├─ camera_tab.py           ✅
      └─ plot_tab.py             ✅
```

---

# 2) Tier 3 的 6 個硬規則（做多媒體不翻車）
1. **UI thread 不抓帧、不做影像重處理**  
2. **顯示 fps 與處理 fps 分離**：例如顯示 20fps、處理 5fps  
3. **回壓策略（backpressure）**：處理跟不上就丟幀（latest-only）  
4. **錄影不要綁死在顯示**：錄影 pipeline 自己跑  
5. **UI 更新要節流**：影像、曲線、log 同時高頻會炸  
6. **平台差異要接受**：Windows/Linux/ARM 的 codec、camera backend 不同

---

# 3) 核心程式碼（Tier3 可貼）

## 3.1 core/multimedia/camera_base.py（統一介面）
```python
from PyQt6.QtCore import QObject, pyqtSignal

class CameraBase(QObject):
    frame = pyqtSignal(object)   # numpy BGR frame or QImage
    state = pyqtSignal(str)      # "RUNNING" / "STOPPED" / "ERROR:..."

    def start(self): raise NotImplementedError
    def stop(self): raise NotImplementedError
```

---

## 3.2 core/multimedia/frame_convert.py（cv BGR → QImage）
```python
import cv2
from PyQt6.QtGui import QImage

def cv_bgr_to_qimage(frame_bgr):
    h, w, ch = frame_bgr.shape
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    bytes_per_line = ch * w
    # copy(): 安全但多一次拷貝（Tier3 先求穩）
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
```

---

## 3.3 core/multimedia/camera_opencv.py（USB Cam：背景 thread 抓帧）
```python
import time, cv2
from PyQt6.QtCore import QThread
from core.multimedia.camera_base import CameraBase

class OpenCVCamera(CameraBase):
    def __init__(self, cam_index=0, grab_fps=30, width=None, height=None):
        super().__init__()
        self.cam_index = cam_index
        self.grab_fps = grab_fps
        self.width = width
        self.height = height
        self._stop = False
        self._thread = None

    def start(self):
        if self._thread is not None:
            return
        self._stop = False
        self._thread = _GrabThread(self)
        self._thread.start()
        self.state.emit("RUNNING")

    def stop(self):
        self._stop = True
        if self._thread:
            self._thread.wait(1000)
        self._thread = None
        self.state.emit("STOPPED")

class _GrabThread(QThread):
    def __init__(self, cam: OpenCVCamera):
        super().__init__()
        self.cam = cam

    def run(self):
        cap = cv2.VideoCapture(self.cam.cam_index)
        if self.cam.width:  cap.set(cv2.CAP_PROP_FRAME_WIDTH,  int(self.cam.width))
        if self.cam.height: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.cam.height))

        interval = 1.0 / max(1, self.cam.grab_fps)

        if not cap.isOpened():
            self.cam.state.emit("ERROR: camera open failed")
            return

        while not self.cam._stop:
            ok, frame = cap.read()
            if ok:
                self.cam.frame.emit(frame)   # ✅ 背景 thread emit
            time.sleep(interval)

        cap.release()
```

---

## 3.4 core/metrics_video.py（影像 FPS / 丟幀 / latency）
```python
import time

class VideoMetrics:
    def __init__(self):
        self.in_frames = 0
        self.drop_frames = 0
        self.last_fps_t = time.time()
        self.fps = 0.0

    def on_in(self):
        self.in_frames += 1
        now = time.time()
        dt = now - self.last_fps_t
        if dt >= 1.0:
            self.fps = self.in_frames / dt
            self.in_frames = 0
            self.last_fps_t = now

    def on_drop(self):
        self.drop_frames += 1
```

---

## 3.5 core/multimedia/recorder_opencv.py（錄影：最小可落地）
> 先提供兩種錄法：  
> A) 最穩：每秒存圖（不吃 codec）  
> B) VideoWriter：寫 mp4/avi（取決於系統 codec）

```python
import os, time, cv2
from pathlib import Path

class ImageRecorder:
    def __init__(self, out_dir="records/img", save_fps=1):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.save_fps = save_fps
        self._last = 0.0
        self.enabled = False

    def start(self):
        self.enabled = True

    def stop(self):
        self.enabled = False

    def on_frame(self, frame_bgr):
        if not self.enabled:
            return
        now = time.time()
        if now - self._last < 1.0 / max(1, self.save_fps):
            return
        self._last = now
        fn = self.out_dir / (time.strftime("%Y%m%d_%H%M%S") + ".jpg")
        cv2.imwrite(str(fn), frame_bgr)

class VideoWriterRecorder:
    def __init__(self, out_path="records/out.avi", fps=20, fourcc="XVID"):
        self.out_path = out_path
        self.fps = fps
        self.fourcc = fourcc
        self.writer = None
        self.enabled = False

    def start(self, width, height):
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)
        cc = cv2.VideoWriter_fourcc(*self.fourcc)
        self.writer = cv2.VideoWriter(self.out_path, cc, float(self.fps), (int(width), int(height)))
        self.enabled = True

    def stop(self):
        self.enabled = False
        if self.writer:
            self.writer.release()
        self.writer = None

    def on_frame(self, frame_bgr):
        if self.enabled and self.writer:
            self.writer.write(frame_bgr)
```

---

# 4) UI：CameraTab（顯示/處理/錄影分離 + 丟幀策略）
## 4.1 ui/tabs/camera_tab.py
> 設計：  
> - Grabber（背景 thread）一直丟 frame 進來  
> - UI 只顯示（節流顯示 fps）  
> - Processor（可選）用 latest-only（處理跟不上就丟幀）  
> - Recorder（可選）獨立節流

```python
import time
from collections import deque

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap

from core.multimedia.camera_opencv import OpenCVCamera
from core.multimedia.frame_convert import cv_bgr_to_qimage
from core.multimedia.recorder_opencv import ImageRecorder
from core.metrics_video import VideoMetrics

class CameraTab(QWidget):
    def __init__(self):
        super().__init__()
        self.metrics = VideoMetrics()

        # UI
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        layout.addLayout(top)

        self.btn_start = QPushButton("Start Camera")
        self.btn_stop  = QPushButton("Stop Camera")
        self.cb_record = QCheckBox("Record (1 fps jpg)")
        self.lb_info   = QLabel("fps=0 drop=0")
        top.addWidget(self.btn_start)
        top.addWidget(self.btn_stop)
        top.addWidget(self.cb_record)
        top.addWidget(self.lb_info)

        self.lb_video = QLabel("No Video")
        self.lb_video.setMinimumHeight(300)
        layout.addWidget(self.lb_video)

        # Camera
        self.cam = OpenCVCamera(cam_index=0, grab_fps=30)
        self.cam.frame.connect(self.on_frame)

        # Recorder（最穩：存圖）
        self.rec = ImageRecorder(out_dir="records/img", save_fps=1)

        # latest-only queue（處理/顯示節流用）
        self.latest = deque(maxlen=1)

        # UI refresh timer（顯示節流）
        self.t_ui = QTimer(self)
        self.t_ui.setInterval(50)  # 20fps 顯示
        self.t_ui.timeout.connect(self.flush_ui)
        self.t_ui.start()

        self.btn_start.clicked.connect(self.start_camera)
        self.btn_stop.clicked.connect(self.stop_camera)
        self.cb_record.toggled.connect(self.toggle_record)

    def start_camera(self):
        self.cam.start()

    def stop_camera(self):
        self.cam.stop()

    def toggle_record(self, on: bool):
        if on: self.rec.start()
        else:  self.rec.stop()

    def on_frame(self, frame_bgr):
        # 背景 thread 來的 frame
        self.metrics.on_in()

        # 最新一幀策略：只留最新（避免堆積延遲爆炸）
        if len(self.latest) == self.latest.maxlen:
            self.metrics.on_drop()
        self.latest.append(frame_bgr)

        # 錄影（獨立節流：1fps）
        self.rec.on_frame(frame_bgr)

    def flush_ui(self):
        if not self.latest:
            return
        frame = self.latest.pop()

        qimg = cv_bgr_to_qimage(frame)
        self.lb_video.setPixmap(QPixmap.fromImage(qimg))

        self.lb_info.setText(f"fps={self.metrics.fps:.1f} drop={self.metrics.drop_frames}")
```

---

# 5) UI：PlotTab（即時曲線的工程做法：資料與顯示分離）
## 5.1 core/plot/plot_buffer.py（ring buffer）
```python
from collections import deque

class PlotBuffer:
    def __init__(self, maxlen=2000):
        self.buf = deque(maxlen=maxlen)

    def push(self, x):
        self.buf.append(x)

    def snapshot(self):
        return list(self.buf)
```

## 5.2 ui/tabs/plot_tab.py（先用 stub，Tier3 重點是節流架構）
> 你要接 pyqtgraph/QtCharts 都行。Tier3 先把「資料流 + 節流」寫對。  
> 這裡用 QLabel 代替真正畫圖（你只要把 `render_plot(points)` 換成你的圖表庫 API 即可）。

```python
import random
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import QTimer
from core.plot.plot_buffer import PlotBuffer

class PlotTab(QWidget):
    def __init__(self):
        super().__init__()
        self.buf = PlotBuffer(maxlen=2000)

        layout = QVBoxLayout(self)
        self.lb = QLabel("plot points: 0")
        self.btn = QPushButton("Inject random data")
        layout.addWidget(self.lb)
        layout.addWidget(self.btn)

        self.btn.clicked.connect(self.inject)

        # UI 刷新節流：100ms
        self.t = QTimer(self)
        self.t.setInterval(100)
        self.t.timeout.connect(self.refresh)
        self.t.start()

    def inject(self):
        # 模擬資料：Tier3 會接 BUS.parsed 或設備資料
        for _ in range(50):
            self.buf.push(random.random())

    def refresh(self):
        pts = self.buf.snapshot()
        self.lb.setText(f"plot points: {len(pts)}")
        # 這裡換成：plot.setData(pts) / series.replace(...)
```

---

# 6) 把 Tab 接回 MainWindow（Tier3：MainWindow 加 TabWidget）
在 `ui/main_window.py` 裡加入（示意片段）：

```python
from PyQt6.QtWidgets import QTabWidget
from ui.tabs.camera_tab import CameraTab
from ui.tabs.plot_tab import PlotTab

tabs = QTabWidget()
tabs.addTab(CameraTab(), "Camera")
tabs.addTab(PlotTab(), "Plot")

layout.addWidget(tabs)   # 放在你原本 table/log 上方或旁邊都行
```

---

# 7) Tier3 的「關鍵調參」：你要用工程腦袋調，不要用感覺
### 建議起手式（保守穩定）
- Grab fps：30
- Display fps：15~20（`t_ui=50~66ms`）
- Process fps：5（用計時/限頻）
- Record fps：1（存圖）或 10（VideoWriter）視 CPU

### 你要看哪些指標？
- `fps` 是否穩定
- `drop_frames` 是否快速增加（表示 UI/處理跟不上）
- UI 是否卡（滑鼠拖曳/點按是否延遲）

---

# 8) Tier3 常見翻車原因（你要避開）
- 在 UI thread 做 OpenCV heavy 處理（Canny/AI/Decode）→ 卡
- 每一幀都處理 + 不丟幀 → 延遲越積越大
- 同時高頻：log + table + plot + video 不節流 → UI 炸
- 錄影跟顯示綁在同 pipeline → 錄影卡就把顯示拖死
- 盲目追求 60fps → 工控 UI 沒必要

---

# 9) Tier3 跑起來的方法
```bash
pip install -r requirements.txt
python main.py
```

> 如果你用 OpenCV camera：你需要裝 opencv  
> - Windows：`pip install opencv-python`  
> - Linux/ARM：可能要 apt 或對應 wheel（取決於平台）  
> Tier3 這份教學先提供 OpenCV 路徑，等你要上 RTSP/GStreamer 再進階。

---

# 10) 下一階（你回我 Tier4）
Tier4 會把整套平台真正「做成可擴展產品」：

- camera/recorder/processor 都 plugin 化（像 Tier2 transport 一樣）
- Processor plugin 支援：頻譜、AI、OCR、異常偵測（可熱插拔）
- 建立最小 CI：tests + style + packaging
- 更嚴謹的 backpressure（processor busy → queued release）
- 設計 replay 的 schema version（資料格式治理）

# Lv8｜多媒體與可視化：Camera / Video / 音訊 / OpenCV / GStreamer（把 Qt 上位機做到「影像＋即時圖＋可錄影」）

Lv7 你已經把「產品骨架」完成：Model/View、FSM、QSettings、Log、打包。  
Lv8 進到你之前問的「多媒體 / 工控」領域裡最硬的一塊：**影像/音訊/錄影/串流 + 即時可視化**。  
這一級的重點不是 API 多，而是**架構與效能邊界**：多媒體處理很容易把 UI 打爆。

---

## Lv8 的教學意義（你在練什麼）

- 讓你做出工控常見功能：
  - 監視器畫面（USB camera / IP camera）
  - 即時顯示 + 錄影
  - 影像處理（OpenCV）+ UI
  - 即時曲線（sensor/頻譜/狀態）
- 讓你理解多媒體的工程關鍵：
  1) **UI thread 不做影像重工作**
  2) **影像資料流要能降頻、降解析度、節流**
  3) **錄影/串流跟顯示是兩條不同的 pipeline**
- 給你一套「可落地」的多媒體架構模板。

---

# Lv8 先背 6 個定錨（做多媒體不翻車的核心）

1. **顯示 ≠ 處理 ≠ 錄影**：三條 pipeline 分開設計
2. **Frame rate 控制**：UI 只要順（例如 30fps 或更低），不是越高越好
3. **Backpressure（回壓）**：處理跟不上就要丟幀，而不是堆積到爆
4. **零拷貝/少拷貝**：影像大量 memcpy 會直接拖垮 CPU
5. **跨 thread 溝通**：signal/slot + queue（Lv6 的延伸）
6. **平台差異**：Windows / Linux / RPi 的 camera backend、編解碼能力差很多

---

# Part A｜Qt Multimedia 基礎：快速做到「顯示相機」與「錄影」

> 注意：Qt Multimedia 在不同 Qt 版本差異較大（Qt5/Qt6 API 不完全相同）。  
> 我這裡以「觀念＋可用骨架」為主，你可以在你的版本上微調名稱。

---

## 範例 1｜Qt6（概念骨架）：顯示 Camera 到視窗

```python
# 觀念骨架：Camera → CaptureSession → VideoOutput → Widget
# 具體 API 名稱可能依 PyQt6/Qt6 版本略不同

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtMultimedia import QCamera
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtMultimedia import QMediaCaptureSession

class CameraView(QWidget):
    def __init__(self):
        super().__init__()
        self.video = QVideoWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.video)

        self.camera = QCamera()
        self.session = QMediaCaptureSession()
        self.session.setCamera(self.camera)
        self.session.setVideoOutput(self.video)

        self.camera.start()
```

**小解釋**
- 這條路最省事：你先把「能顯示」做出來
- 但「影像處理」通常不會直接在這條顯示 pipeline 上做（後面會教 OpenCV pipeline）

---

## 範例 2｜Qt6（概念骨架）：錄影（Display + Record 分離）

```python
from PyQt6.QtMultimedia import QMediaRecorder

self.recorder = QMediaRecorder()
self.session.setRecorder(self.recorder)

def start_record(path: str):
    self.recorder.setOutputLocation(path)
    self.recorder.record()

def stop_record():
    self.recorder.stop()
```

**工程重點**
- 你要把「錄影」當成另一條 pipeline（甚至另一個進程）  
- 否則 UI 刷新、處理、錄影互相干擾，很容易抖或掉幀

---

# Part B｜OpenCV + Qt：工控最常用（顯示 + 處理 + 不卡 UI）

很多人會直接用 OpenCV `cv2.VideoCapture`，然後在 UI thread while 讀，直接翻車。  
正解：**抓帧在背景 thread，UI 只顯示**。

---

## 範例 3｜把 OpenCV frame 轉成 QImage（最常用工具函數）

```python
import cv2
from PyQt6.QtGui import QImage

def cv_bgr_to_qimage(frame_bgr):
    h, w, ch = frame_bgr.shape
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    bytes_per_line = ch * w
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
```

**注意**
- `.copy()` 是為了避免底層 buffer 被釋放後 QImage 指到無效記憶體
- 這是安全做法，但會多一次拷貝（你要在效能與安全之間取捨）

---

## 範例 4｜背景 thread 抓帧，UI 用 signal 顯示（最標準骨架）

```python
import cv2, time
from PyQt6.QtCore import QObject, pyqtSignal, QThread

class CvGrabber(QObject):
    frame = pyqtSignal(object)     # 發送 numpy array（BGR）
    finished = pyqtSignal()

    def __init__(self, cam_index=0, fps=30):
        super().__init__()
        self.cam_index = cam_index
        self.fps = fps
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        cap = cv2.VideoCapture(self.cam_index)
        interval = 1.0 / max(1, self.fps)

        while not self._stop:
            ok, frame = cap.read()
            if ok:
                self.frame.emit(frame)  # ✅ 背景 thread 發 signal
            time.sleep(interval)

        cap.release()
        self.finished.emit()
```

UI 端：

```python
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap

label = QLabel()

thread = QThread()
grab = CvGrabber(0, fps=30)
grab.moveToThread(thread)

thread.started.connect(grab.run)
grab.frame.connect(lambda f: label.setPixmap(QPixmap.fromImage(cv_bgr_to_qimage(f))))
grab.finished.connect(thread.quit)
grab.finished.connect(grab.deleteLater)
thread.finished.connect(thread.deleteLater)

thread.start()
```

**工程重點**
- UI thread 只做：把 QImage 變 QPixmap 顯示
- 抓帧在背景 thread，不卡 UI

---

## 範例 5｜加上「丟幀」策略：處理跟不上就丟（避免堆爆）

當你還想做影像處理（例如邊緣、物件偵測、OCR），可能比 30fps 慢很多。  
這時你不能把每一幀都排隊處理，會越積越多，最後爆掉。

最常用策略：**只保留最新一幀（latest-only）**。

```python
from collections import deque

latest = deque(maxlen=1)

def on_frame(frame):
    latest.append(frame)

grab.frame.connect(on_frame)

# UI 用 QTimer 每 33ms 取最新一幀顯示（也可以在另一個 worker 取來處理）
```

---

## 範例 6｜影像處理 worker（背景 thread），輸出疊圖結果回 UI

```python
import cv2
from PyQt6.QtCore import QObject, pyqtSignal

class CvProcessor(QObject):
    out = pyqtSignal(object)   # processed frame (BGR)

    def process(self, frame):
        # 例：灰階 + 邊緣
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edge = cv2.Canny(gray, 60, 120)
        out = cv2.cvtColor(edge, cv2.COLOR_GRAY2BGR)
        self.out.emit(out)
```

連接方式（重點是跨 thread）：

```python
proc_thread = QThread()
proc = CvProcessor()
proc.moveToThread(proc_thread)
proc_thread.start()

# grabber frame → proc.process（跨 thread）
grab.frame.connect(proc.process)

# proc out → UI 顯示
proc.out.connect(lambda f: label.setPixmap(QPixmap.fromImage(cv_bgr_to_qimage(f))))
```

---

# Part C｜GStreamer（Linux / Embedded 常見）：最強的多媒體管線思維

如果你做：
- IP Camera（RTSP）
- H.264/H.265 編解碼
- 低延遲串流
- 同時顯示 + 錄影 + 推論

GStreamer 很常是正解。Qt 有時候只是「顯示層」，真正的 pipeline 用 GStreamer。

---

## 範例 7｜用 GStreamer 命令理解 pipeline（概念）

- 顯示 USB Camera：

```bash
gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! autovideosink
```

- RTSP 顯示（概念）：

```bash
gst-launch-1.0 rtspsrc location=rtsp://... latency=0 ! decodebin ! videoconvert ! autovideosink
```

**工程重點**
- pipeline 是「資料流設計」：source → decode → convert → sink
- 你真正要練的是「把顯示、錄影、推論分流」

---

## 範例 8｜Qt 端只做顯示：用 QProcess 啟動 GStreamer（工程實務常見）

```python
from PyQt6.QtCore import QProcess

proc = QProcess()
proc.start("gst-launch-1.0", [
    "v4l2src", "device=/dev/video0", "!",
    "videoconvert", "!",
    "autovideosink"
])
```

**說明**
- 這是「外部 pipeline」思維：Qt 不負責重活，Qt 只管理 UI 與控制
- 工控很多產品就是這樣做：穩、好維護、好換後端

---

# Part D｜即時曲線 / 圖表：感測器/頻譜/狀態監控

Qt 自帶的 `Qt Charts` 或第三方（如 pyqtgraph）都能做。  
核心問題不是畫圖 API，而是：**資料更新不要太頻繁**。

---

## 範例 9｜簡單的「批次刷新」策略（Lv6 的延伸）

- 背景 thread 不斷產生數據（例如每 5ms 一筆）
- UI 每 50~100ms 才刷新一次（人眼也看不出更快）

```python
from collections import deque
from PyQt6.QtCore import QTimer
import time, random

dataq = deque(maxlen=2000)

def on_new_data(x):
    dataq.append(x)

# 假裝背景資料源（實務上你會用 thread emit signal）
for _ in range(100):
    on_new_data(random.random())

timer = QTimer()
timer.setInterval(100)

def refresh_plot():
    # 取出目前資料畫一次（示意：這裡不依賴特定圖表庫）
    # 真實：line_series.replace([...]) 或 plot.setData(...)
    print("refresh points:", len(dataq))

timer.timeout.connect(refresh_plot)
timer.start()
```

**工程重點**
- UI 刷新頻率要「夠用」就好
- 把資料與顯示 decouple，才能穩

---

# Part E｜多媒體 + 工控：把「控制」與「視覺」整合到同一套架構

典型工控上位機最常見的整體架構：

- Driver（Serial/TCP/CAN/Modbus）→ Parser → State Machine
- Camera pipeline（grab/stream）→ Processor（可選）→ UI display
- Recorder pipeline（可選）→ File writer
- UI 層：只顯示與操作
- Settings：保存所有配置
- Logging：全程可追

---

## 範例 10｜「雙管線」：顯示 15fps、處理 5fps（常用降頻策略）

你可能想顯示順，但處理（例如 AI）不用那麼頻繁。

```python
import time
last_proc = 0.0

def on_frame(frame):
    global last_proc
    # 顯示：每幀都顯示（或 15fps）
    show(frame)

    # 處理：限頻 5fps
    now = time.time()
    if now - last_proc >= 0.2:
        last_proc = now
        send_to_processor(frame)
```

**工程重點**
- 顯示與處理分開節流
- 不要「所有幀都跑 AI」

---

# Part F｜效能與資源：你會遇到的「平台差異」

你之前問「裝 Qt 在 Windows 跟樹莓派會差很多嗎？ARM 會被限制嗎？」

結論（工程角度）：
- Qt 本身多平台，但 **多媒體後端與編解碼能力差很大**
- 樹莓派/ARM：
  - 有些 opencv wheel / pytorch wheel 版本限制（取決於架構與 python 版本）
  - 編解碼可能要走硬體（V4L2 / OMX / VAAPI / NVDEC 等）
- Windows：
  - camera backend、DirectShow/MediaFoundation 影響可用性
  - 打包時 Qt plugins 非常關鍵（platforms、imageformats）

**你要練的不是「能不能裝」，而是：**
- 版本/架構匹配（x64 vs arm64）
- 後端選擇（Qt Multimedia vs OpenCV vs GStreamer）
- pipeline 分離（顯示/錄影/推論各自獨立）

---

# Lv8 常見錯誤（多媒體最容易翻的點）

- UI thread while 讀 camera → 直接卡死
- 每幀都做 heavy processing → 排隊堆積 → 延遲爆炸
- 顯示與錄影同一條 pipeline 沒分流 → 互相拖累
- UI 更新太頻繁（log/圖/影像同時高頻）→ UI 仍然卡
- 沒有丟幀策略 → 系統只會越來越慢

---

# Lv8 小作業（做完你就能做監控/工控多媒體上位機）

做一個「Camera + 處理 + 錄影」骨架（可先用假錄影/存圖取代）：

1. 背景 thread 抓帧（OpenCV 或 Qt Multimedia）
2. UI 顯示（15~30fps）
3. 背景 thread 做處理（5fps，限頻 + 丟幀策略）
4. log 顯示處理結果（批次刷新）
5. QSettings 保存 camera index、fps、處理開關
6. Start/Stop 控制整條 pipeline
7. （加分）錄影：每秒存一張或寫入影片檔

---

## Lv8 結尾：你真正學到的是什麼？

Lv8 不是「把影像顯示出來」而已，你學到的是多媒體工程的核心：

- 影像是「資料流」：要分 pipeline、要節流、要回壓、要丟幀
- UI 只是顯示層：永遠不做重活
- thread 只是工具：真正的穩定來自架構

如果你要 Lv9，通常就是：
- **插件化（plugin）把 Driver/Processor 做成可熱插拔**
- **測試/CI、效能 profiling、記憶體洩漏追蹤**
- **跨平台部署（Windows/Linux/ARM）一致化**

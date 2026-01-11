# Lv6｜Thread：讓 UI 永遠不卡的最後一塊拼圖（Qt 正確模型＋大量範例）

Lv5 你已經能用 readyRead 穩定收資料，但你很快會遇到下一個瓶頸：

> **不是在等資料卡住，而是資料處理太慢卡住。**

Lv6 就是解這個：把重工作移出 UI thread，UI 只負責事件迴圈、顯示與互動。

---

## Lv6 的教學意義（你在練什麼）

- 你要學會「UI thread 的工作邊界」：UI 只能做輕量、即時回應。
- 你要學會 Qt 的正確 Thread 模型：
  - `QThread` 是執行環境（可有 event loop）
  - `Worker(QObject)` 才是工作本體
  - `moveToThread()` 是把物件的 slot 轉去背景 thread 執行
- 你要學會跨 thread 溝通的唯一正解：**signal/slot**
- 你要知道為什麼不建議亂用 `threading.Thread` 直接改 UI：會隨機 crash

---

## Lv6 先背三鐵則（最重要）

1. **UI 只能在主執行緒**（只在 UI thread 更新 Widget）
2. **背景 thread 不碰 UI**
3. **跨 thread 用 signal/slot 回傳結果**（Qt 會排隊，安全）

---

## 你問過的：UI 不要 context switch 會比較穩？

是。Qt 的策略就是「UI 單執行緒」：

- UI 的正確性很依賴「一致的更新順序」
- 多 thread 同時改 UI 會造成 race condition：不是每次出錯、但會隨機出錯
- 隨機出錯是工程最痛的 bug

所以 Qt 讓你：
- UI thread 專心跑 event loop
- 重工作丟背景 thread
- 結果用 signal 回來更新 UI

---

# 範例區（Lv6：從最小模型到工控常用架構）

---

## 範例 1｜最小正確 QThread + Worker（計算重工作）

### 1) Worker：只算，不碰 UI

```python
from PyQt6.QtCore import QObject, QThread, pyqtSignal

class SumWorker(QObject):
    result = pyqtSignal(int)
    finished = pyqtSignal()

    def do_work(self):
        s = 0
        for i in range(20_000_000):
            s += i
        self.result.emit(s)
        self.finished.emit()
```

### 2) UI 端：啟動 thread、接收結果

```python
# 假設你在某個按鈕 click 裡做：
thread = QThread()
worker = SumWorker()
worker.moveToThread(thread)

thread.started.connect(worker.do_work)

worker.result.connect(lambda v: label.setText(str(v)))  # ✅ UI thread 更新 UI
worker.finished.connect(thread.quit)
worker.finished.connect(worker.deleteLater)
thread.finished.connect(thread.deleteLater)

thread.start()
```

**小解釋**
- `do_work` 在背景 thread 跑，不會卡 UI
- `result` 會排隊回 UI thread 執行 slot
- `deleteLater()` 是避免記憶體洩漏與生命週期問題

---

## 範例 2｜可停止的 Worker（工控常見：長時間任務要能停）

### Worker 支援 stop flag

```python
import time
from PyQt6.QtCore import QObject, pyqtSignal

class LoopWorker(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        p = 0
        while not self._stop and p <= 100:
            time.sleep(0.05)     # 注意：在背景 thread sleep OK
            self.progress.emit(p)
            p += 1
        self.finished.emit()
```

### UI 端：Start / Stop

```python
thread = QThread()
worker = LoopWorker()
worker.moveToThread(thread)

thread.started.connect(worker.run)
worker.progress.connect(progress_bar.setValue)
worker.finished.connect(thread.quit)

btn_stop.clicked.connect(worker.stop)

worker.finished.connect(worker.deleteLater)
thread.finished.connect(thread.deleteLater)

thread.start()
```

---

## 範例 3｜為什麼不用 threading.Thread？（你會踩到的地雷）

### 錯誤示範：背景 thread 直接改 UI（危險）

```python
import threading

def background():
    label.setText("hi")  # ❌ 這是 UI 物件，非 thread-safe

threading.Thread(target=background).start()
```

可能的後果：
- 有時候看起來正常
- 某些負載下突然 crash（最難 debug）

**Qt 正解**：背景算完 emit signal 回 UI。

---

## 範例 4｜Qt 的「物件歸屬」：moveToThread 不是跑函數，是換歸屬

你問過：「為什麼用 moveToThread？不是跑函數？」

重點是：
- Qt 的 signal/slot + event loop 會依照 **QObject 所屬 thread** 來決定 slot 在哪個 thread 執行
- `moveToThread` 是把 Worker 的 slot 執行位置切到背景 thread

> QThread 是環境，Worker 才是工作；moveToThread 決定工作在哪跑。

---

## 範例 5｜工控常見：I/O 收資料快，但解析很重 → 解析丟 thread

Lv5 你已經知道 readyRead 不能做重工作。這裡把它落地：

### (A) UI thread：Driver 收 raw bytes（快）

```python
# driver.readyRead: 只做 readAll + buffer + framing
# 拆出 frame 後 emit frame_received(bytes)
```

### (B) 背景 thread：Parser 做 heavy parse（慢）

```python
from PyQt6.QtCore import QObject, pyqtSignal

class HeavyParser(QObject):
    parsed = pyqtSignal(dict)

    def parse_frame(self, frame: bytes):
        # 假裝很慢的解析
        # 例如：解壓縮、CRC、轉浮點、頻譜計算、AI 推論...
        data = {"len": len(frame), "hex": frame[:8].hex()}
        self.parsed.emit(data)
```

### (C) 連接：Driver → Parser(背景) → UI

```python
# 建 thread
parse_thread = QThread()
parser = HeavyParser()
parser.moveToThread(parse_thread)
parse_thread.start()

# Driver 收到 frame 後，把 frame 丟給 parser.parse_frame（跨 thread slot）
driver.frame_received.connect(parser.parse_frame)

# parser 結果回 UI 更新
parser.parsed.connect(lambda d: ui_log.appendPlainText(str(d)))
```

**工程解釋**
- Driver 繼續穩定收資料（不被 heavy parse 拖慢）
- Heavy parse 在背景跑
- UI 只收結果顯示

---

## 範例 6｜QThreadPool / QRunnable：大量短任務更適合這個

如果你有很多短任務（例如一次解析很多檔案、圖片批次處理），不建議每次都 new QThread。

概念示範：

```python
from PyQt6.QtCore import QRunnable, QThreadPool, QObject, pyqtSignal

class Emitter(QObject):
    done = pyqtSignal(str)

class Task(QRunnable):
    def __init__(self, emitter: Emitter, payload: str):
        super().__init__()
        self.emitter = emitter
        self.payload = payload

    def run(self):
        # 重工作
        out = self.payload.upper()
        self.emitter.done.emit(out)

pool = QThreadPool.globalInstance()
em = Emitter()
em.done.connect(lambda s: print("result:", s))

pool.start(Task(em, "abc"))
pool.start(Task(em, "def"))
```

**小解釋**
- ThreadPool 會重用背景 thread，減少建立成本
- 依然用 signal 回主執行緒（安全）

---

## 範例 7｜避免 UI 爆量更新：用 buffer + QTimer 合併刷新（工控很常用）

即使解析在背景很快，如果你每一筆資料都立刻更新 UI：
- UI 也會被刷爆（例如每秒 500 筆 log）

解法：背景 thread 把資料丟到 queue，UI 用 QTimer 每 100ms 批次刷新。

```python
from collections import deque
from PyQt6.QtCore import QTimer

pending = deque()

def on_parsed(d):
    pending.append(d)

parser.parsed.connect(on_parsed)

ui_timer = QTimer()
ui_timer.setInterval(100)
ui_timer.timeout.connect(lambda: flush_ui())
ui_timer.start()

def flush_ui():
    # 每次最多刷 50 筆，避免 UI 卡
    for _ in range(min(50, len(pending))):
        d = pending.popleft()
        ui_log.appendPlainText(str(d))
```

---

## 範例 8｜Thread 的生命週期：關閉視窗要安全停止背景工作

工控上位機很常：
- 關程式時要停 thread、關 socket、關 serial、寫檔 flush

基本習慣：
- 視窗 closeEvent 裡要求 worker stop
- thread.quit + wait（或用 finished signal 收尾）

示意：

```python
def closeEvent(self, e):
    worker.stop()
    thread.quit()
    thread.wait(1000)   # 最多等 1 秒
    e.accept()
```

（注意：`wait` 會阻塞 UI，但在關閉流程通常可接受；更完整做法可用非阻塞關閉策略。）

---

## Lv6 常見地雷（你一定要避開）

- 背景 thread 直接改 UI（最危險）
- 在背景 thread 裡寫 while 忙等（回到錯誤架構）
- 忘記 quit / deleteLater（資源泄漏）
- background 太快 → UI 更新太頻繁（用批次刷新）

---

## Lv6 小作業（做完你就能上多媒體/工控專案）

做一個「資料解析器 UI」：

- Driver（假資料也行）每秒產生 200 筆 frame（bytes）
- Parser 在背景 thread 把 frame 轉成 dict（模擬 heavy）
- UI 用 QTimer 每 100ms 批次顯示最多 50 筆到 log
- Start/Stop 控制整個 pipeline

**要求**
- UI thread 不准卡
- 任何重工作都在背景 thread
- UI 更新要節流（batch）

---

## Lv6 結尾：你真正學到的是什麼？

你學到的是 Qt 工程的終極分工：

- **UI thread：事件迴圈 + 顯示 + 互動（永遠要順）**
- **背景 thread：重運算/重解析/多媒體處理（可以慢，但不能卡 UI）**
- **signal/slot：跨 thread 的安全橋梁**

到這裡，你 Lv1～Lv6 的「工程骨架」就完整了。

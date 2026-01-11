# Lv4｜QTimer：它是「排程事件」的定時器，不是 RTOS，也不是用來等資料的工具

Lv3 你已經有事件思維；Lv4 要學的是：  
**週期性工作在 GUI 世界要用 QTimer**，但你要很清楚它的能力邊界——不然就會拿它做錯事（例如「拿 QTimer 等資料」）。

---

## Lv4 的教學意義（你在練什麼）

- 讓你用「事件排程」做週期性任務，而不是 while + sleep。
- 讓你理解 QTimer 的時間特性：**會抖動**、**不搶佔**、**受事件迴圈負載影響**。
- 回答你問的：
  - `QTimer` 為什麼不能約略等同 RTOS？
  - 為什麼 RTOS 不適合 UI？
  - 為什麼 UI 不要 context switch 反而更穩？
- 建立工控常用用法：UI refresh、狀態檢查、軟 watchdog、低頻掃描。

---

## 先把結論講清楚（你先背）

1. **QTimer = 到時間就丟一個 timeout 事件進 event loop**
2. **它不是硬體 timer、不是搶佔式、不是 deterministic**
3. **它適合「允許抖動」的週期性工作**
4. **它不適合精準控制，也不適合拿來「等資料」**

---

## QTimer 的本質是什麼？

你可以這樣理解：

> QTimer 不是「準時執行」，而是「準時提醒」：提醒會排隊，等 UI thread 有空才處理。

所以如果 UI thread 正在忙：
- timeout 事件可能被延後
- 或者多個 timeout 堆在一起（你就會看到卡頓、跳動）

---

## 為什麼 QTimer 不能約略等同 RTOS？

你問過這題，這裡用工程語言講一次就懂。

### RTOS（Preemptive）
- 多 task
- 有優先權
- 可能搶佔（context switch）
- 目標：**確定性（determinism）與即時性（real-time）**

### QTimer（Event scheduled）
- 通常只有一個 UI thread
- 不搶佔、不切 context
- 目標：**UI 的穩定與一致性**

所以：
- QTimer 可以「定期做事」
- 但它不保證「硬準時」
- 你不能拿它當 MCU timer / RTOS tick

---

## 為什麼 RTOS 不適合 UI？（你問過）

你說：「但我 RTOS 如果把優先級設好、時間給充足，不也能保證某些事情一定執行完？」

**在控制/資料處理領域，你這句成立。**  
但 UI 領域會遇到不同的問題：

1) **UI 不是 thread-safe**
- 多 task 同時碰 UI 資料結構（Widget/Scene）→ race → 隨機 crash
- 你再怎麼設優先級，也避免不了「同一時間兩個 task 寫畫面」這種事故

2) **UI 的需求不是硬即時，而是「一致性 + 不卡」**
- 人眼看 30~60 FPS 就很順
- 更重要的是「畫面不要亂、不要閃、不要卡」

3) **Context switch 帶來複雜度**
- UI bug 常常不是「一定發生」，是「負載高才發生」
- 這種 bug 最難抓，工程風險很高

所以 Qt 的策略是：
- **UI 單執行緒**（避免競態）
- 重工作丟到背景 thread（Lv6）

> 你的直覺「UI 事情不要 context switch 反而更穩」基本正確：  
> Qt 就是把 UI 維持在單線程，避免不可控的交錯。

---

# 範例區（Lv4：QTimer 的常用工程寫法）

---

## 範例 1｜最基本 QTimer：每 200ms 更新 UI（典型 UI refresh）

```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import QTimer
from datetime import datetime

class UiRefreshDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.label = QLabel("...")
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start()

    def on_tick(self):
        self.label.setText(datetime.now().strftime("%H:%M:%S.%f")[:-3])

app = QApplication(sys.argv)
w = UiRefreshDemo()
w.show()
sys.exit(app.exec())
```

**小解釋**
- 200ms 這種頻率很適合 UI 顯示（5Hz）
- 你不追求精準毫秒，只追求不卡、穩定更新

---

## 範例 2｜QTimer.singleShot：延遲初始化（避免視窗 show 前卡住）

很多工程會這樣做：先 show 視窗，再做一些初始化（掃設備、讀設定檔）。

```python
from PyQt6.QtCore import QTimer

def init_after_show():
    print("視窗顯示後才做初始化（UI 不會一開始就卡）")

QTimer.singleShot(0, init_after_show)   # 0 = 下一輪事件迴圈立刻做
```

**小解釋**
- `singleShot(0, ...)` 是一個「讓出控制權」技巧
- 先讓 Qt 畫面完成，再做工作

---

## 範例 3｜Start/Stop Timer：按鈕控制週期工作

```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout
from PyQt6.QtCore import QTimer

class TimerControl(QWidget):
    def __init__(self):
        super().__init__()
        self.label = QLabel("stopped")
        self.btn_start = QPushButton("Start")
        self.btn_stop = QPushButton("Stop")

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_stop)

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.on_tick)

        self.btn_start.clicked.connect(self.timer.start)
        self.btn_stop.clicked.connect(self.timer.stop)

    def on_tick(self):
        self.label.setText("tick")

app = QApplication(sys.argv)
w = TimerControl()
w.show()
sys.exit(app.exec())
```

---

## 範例 4｜「軟 watchdog」：每秒檢查一次心跳（工控很常用）

假設你的 Driver 會定期收到心跳資料，每次收到就更新 `last_ms`。  
Timer 每秒檢查一次「多久沒心跳」，超過就顯示斷線。

```python
import sys, time
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton
from PyQt6.QtCore import QTimer

class SoftWatchdog(QWidget):
    def __init__(self):
        super().__init__()
        self.label = QLabel("status: unknown")
        self.btn_fake_beat = QPushButton("Fake heartbeat")

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.btn_fake_beat)

        self.last = time.time()

        self.btn_fake_beat.clicked.connect(self.on_heartbeat)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.check)
        self.timer.start()

    def on_heartbeat(self):
        self.last = time.time()
        self.label.setText("status: alive (heartbeat)")

    def check(self):
        dt = time.time() - self.last
        if dt > 3.0:
            self.label.setText(f"status: timeout ({dt:.1f}s)")
        else:
            self.label.setText(f"status: ok ({dt:.1f}s since beat)")

app = QApplication(sys.argv)
w = SoftWatchdog()
w.show()
sys.exit(app.exec())
```

**小解釋**
- Timer 很適合做「低頻檢查」
- 真正的資料接收仍然應該用 readyRead（Lv5）

---

## 範例 5｜量測 timer 抖動（讓你親眼看到：它不是硬即時）

```python
import sys, time
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import QTimer

class JitterDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.label = QLabel("...")
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

        self.prev = time.perf_counter()

        self.timer = QTimer(self)
        self.timer.setInterval(20)          # 50Hz
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def tick(self):
        now = time.perf_counter()
        dt_ms = (now - self.prev) * 1000
        self.prev = now
        self.label.setText(f"dt = {dt_ms:.2f} ms")

app = QApplication(sys.argv)
w = JitterDemo()
w.show()
sys.exit(app.exec())
```

你會看到：
- dt 不會永遠等於 20ms（會抖）
- 當 UI 或系統忙，dt 會飄得更明顯

---

## 範例 6｜錯誤示範：在 timeout 做重運算（會讓 timer 堆積）

```python
def on_tick():
    # ❌ 重工作塞在 UI thread 的 timer callback
    for _ in range(50_000_000):
        pass
```

結果：
- timer 事件堆積
- UI 卡、輸入不回應
- 看起來像「timer 不準」其實是你把 event loop 卡住

**正解方向**：重運算丟 thread（Lv6）。

---

## 範例 7｜錯誤示範：用 QTimer 等資料（輪詢）

```python
# ❌ 假設每 50ms 去查一次「有沒有資料」
timer.setInterval(50)
timer.timeout.connect(lambda: poll_read())
```

為什麼工程上不建議：
- 延遲不可控：資料可能早到你晚處理
- 大量資料容易堆積，掉包
- 本質是輪詢：你只是把 while 輪詢換成 timer 輪詢

**正解**：用 readyRead（Lv5）。

---

## Lv4 常見錯誤（你避開就很強）

- 用 QTimer 做精準控制（控制迴路、取樣、PWM）
- 把重運算放進 timeout
- 用 QTimer 取代 I/O 事件（拿來等資料）

---

## Lv4 小作業（做一次你就懂）

1) 做一個 UI：
- 兩個 Label：顯示「現在時間」與「timer dt」
- 一個 Start/Stop 控制 timer
2) timer interval 設 20ms
3) 顯示實際 dt，觀察抖動
4) 再加一個按鈕「做重工作」：按下去跑大迴圈
5) 觀察 dt 立刻飄（理解：UI thread 忙會影響 timer）

---

## Lv4 結尾：你真正學到的是什麼？

你學到的是「Qt 的時間觀」：

- QTimer 是事件排程，不是硬即時定時器
- UI 穩定靠單執行緒一致性，不靠 RTOS 搶佔
- 週期性工作可以用 timer，但 I/O 等資料要用事件（readyRead）

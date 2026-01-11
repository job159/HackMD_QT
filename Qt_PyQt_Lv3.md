# Lv3｜Signal / Slot：Qt 的靈魂＝「事件通知」不是「函數命令」

Lv3 是真正的分水嶺：  
你如果把 Signal/Slot 想成「另一種 function call」，你後面 Lv4~Lv6 會一直卡住。  
你如果真的理解 Signal/Slot，你的 GUI 會突然變得很「工程化」：可插拔、可擴充、不怕改。

---

## Lv3 的教學意義（你在練什麼）

- 把「命令式思維」換成「事件式思維」
- 學會解耦：UI 不知道邏輯怎麼做，邏輯也不需要知道 UI 長什麼樣
- 讓一個事件可以同時觸發多個反應（寫 log、更新畫面、觸發流程）
- 為 Lv6（跨執行緒）做底：跨 thread 只能靠 signal 安全回 UI

---

## 先回答你問過的 3 題（用工程角度講清楚）

### 1) 為什麼 signal ≠ function call？

**function call（函數呼叫）**：你「命令」某個函數立刻做事，通常同步、阻塞。

```python
do_action()  # 你叫它做，它就做，做完才回來
```

**signal（訊號）**：你「廣播」某個事件發生了，誰要反應由 connect 決定。

```python
clicked.emit()   # 事件發生了（通知），不是命令誰做什麼
```

**差別的工程結果：**
- function call：容易耦合、容易阻塞 UI
- signal：低耦合、可多人監聽、可跨 thread 安全排隊

---

### 2) 為什麼 Qt 不讓你直接 override onclick？

如果「點擊就一定 override」會帶來工程問題：

- 行為被寫死在某個子類 → 想加第二個反應要改原類（高風險）
- 很難組裝：同一顆按鈕在不同模式要接不同流程
- 不利測試：事件處理散落在子類 override 裡不易替換

Qt 的設計就是：
- UI 事件 = signal  
- 你想怎麼反應 = slot（可替換、可串接、可多人監聽）

你仍然可以 override 底層 event（例如 `mousePressEvent`），但那是更底層、更容易搞錯語意。

---

### 3) 為什麼 signal 可以接多個 slot？

因為 Qt 的 signal/slot 本質就是 **Observer Pattern（觀察者模式）**：

一個事件可能要做很多事：
- 更新 UI
- 寫 log
- 更新狀態機
- 觸發下一步流程

如果全部塞在一個 onclick 裡：
- 會變成巨大的大雜燴函數

signal/slot 讓你把反應拆開：
- 模組化
- 可插拔
- 可新增不改舊（降低回歸風險）

---

# 觀念打底：function call 到底是什麼意思？

你問過：「Function call 是甚麼意思？C 基本上一般函數都叫 function call?」

答案：**是**。只要你寫：

```c
foo();
```

這就是 function call（函數呼叫）。Python 也是：

```python
foo()
```

它的特性就是：呼叫者會跳到函數去跑，跑完再回來（同步）。

---

# 範例區（Lv3：範例要多，從最直覺一路到工程化）

---

## 範例 1｜最基本 connect：按鈕點擊

```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

app = QApplication(sys.argv)

w = QWidget()
btn = QPushButton("Click")

def on_click():
    print("clicked!")

btn.clicked.connect(on_click)

layout = QVBoxLayout(w)
layout.addWidget(btn)

w.show()
sys.exit(app.exec())
```

**小解釋**
- `clicked` 是事件（signal）
- `on_click` 是反應（slot）
- connect 就是「訂閱」

---

## 範例 2｜同一個 signal 接多個 slot（你問的重點）

```python
def update_ui():
    print("update ui")

def write_log():
    print("write log")

def trigger_flow():
    print("trigger flow")

btn.clicked.connect(update_ui)
btn.clicked.connect(write_log)
btn.clicked.connect(trigger_flow)
```

**小解釋**
- 點一次按鈕，三個反應都會跑
- 你不用把三件事塞在同一個大函數

---

## 範例 3｜同一個 slot 被多個 signal 觸發（很常用）

```python
btn_start.clicked.connect(trigger_flow)
btn_stop.clicked.connect(trigger_flow)
```

工程用法：
- Start/Stop 都走同一個流程入口，由內部判斷狀態

---

## 範例 4｜用 lambda 帶參數（快速但要節制）

```python
btn1.clicked.connect(lambda: print("btn1"))
btn2.clicked.connect(lambda: print("btn2"))
```

**注意**
- lambda 很方便，但過度使用會讓除錯變難
- 大型專案建議改成清楚的函數/方法

---

## 範例 5｜自訂 signal（工控/上位機超常用）

你不要讓 UI 直接呼叫 Driver。  
UI 只發出「需求事件」，Driver/Controller 負責做事。

```python
from PyQt6.QtCore import QObject, pyqtSignal

class ControlPanel(QObject):
    connect_requested = pyqtSignal(str, int)  # ip, port
    disconnect_requested = pyqtSignal()

panel = ControlPanel()

# UI 某處：
# panel.connect_requested.emit("192.168.1.10", 502)
```

**小解釋**
- 你用 signal 表達「需求」，不是「呼叫某個 driver 方法」
- 這樣 UI 跟 driver 解耦：換 TCP / 換 Serial 都不用改 UI

---

## 範例 6｜把自訂 signal 放在 QWidget 裡（最常見）

```python
from PyQt6.QtWidgets import QWidget, QPushButton, QLineEdit, QFormLayout
from PyQt6.QtCore import pyqtSignal

class ConnectPanel(QWidget):
    connect_requested = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.ip = QLineEdit("192.168.1.10")
        self.port = QLineEdit("502")
        self.btn = QPushButton("Connect")

        form = QFormLayout(self)
        form.addRow("IP", self.ip)
        form.addRow("Port", self.port)
        form.addRow(self.btn)

        self.btn.clicked.connect(self._emit_connect)

    def _emit_connect(self):
        ip = self.ip.text().strip()
        port = int(self.port.text())
        self.connect_requested.emit(ip, port)
```

**小解釋**
- `ConnectPanel` 只負責輸入與發事件，不做連線
- 這就是「UI 只做顯示/輸入」的落地

---

## 範例 7｜Controller 接 signal 做事（UI 與邏輯分離）

```python
from PyQt6.QtCore import QObject

class Controller(QObject):
    def __init__(self, ui_panel, log):
        super().__init__()
        ui_panel.connect_requested.connect(self.on_connect)
        self.log = log

    def on_connect(self, ip: str, port: int):
        self.log.appendPlainText(f"connect to {ip}:{port}")
        # 真實專案：啟動 driver、進入狀態機
```

**小解釋**
- UI 不知道 Controller 在幹嘛
- Controller 也不需要知道 UI 長什麼樣（只收 signal）

---

## 範例 8｜Signal 鏈式轉送（大型架構很常見）

某個 driver 收到資料 → 發 `data_received`  
Parser 收到資料 → 發 `frame_decoded`  
UI 收到 frame → 更新畫面

```python
from PyQt6.QtCore import QObject, pyqtSignal

class Driver(QObject):
    data_received = pyqtSignal(bytes)

class Parser(QObject):
    frame_decoded = pyqtSignal(dict)

    def __init__(self, driver: Driver):
        super().__init__()
        driver.data_received.connect(self.on_raw)

    def on_raw(self, raw: bytes):
        # 假裝解析
        self.frame_decoded.emit({"len": len(raw)})

class UI(QObject):
    def __init__(self, parser: Parser):
        super().__init__()
        parser.frame_decoded.connect(self.on_frame)

    def on_frame(self, frame: dict):
        print("frame:", frame)
```

**小解釋**
- 這就是工程化「pipeline」
- 任何一層要換掉都可以，不會牽一髮動全身

---

## 範例 9｜Signal 的「排隊」概念（為 Lv6 打底）

你現在先記住一句話：

> **跨執行緒的 signal 會排隊（Queued），slot 會在目標執行緒的 event loop 裡跑。**

你暫時不需要背細節，但你要知道：  
這就是為什麼 Qt 用 signal 能安全跨 thread，而不是直接 function call。

---

## Lv3 常見錯誤（你避開就直接升級）

- 把 signal 當 function call：以為 emit 後就「立刻完成全部工作」
- slot 裡做重運算或阻塞 I/O → UI 卡死
- 把 UI 直接綁死在 driver 方法：UI 一改 driver 跟著改

---

## Lv3 小作業（做一次就會）

1. 做一個 UI：
   - 兩個按鈕：Start / Stop
   - 一個 log 區（QPlainTextEdit）
2. Start 點下去要同時：
   - 更新狀態 label
   - 寫 log
   - 觸發 controller 的 start_flow（用 signal 接）
3. Stop 同理

**要求**
- Start 的 signal 至少接 2 個 slot（練 Observer）
- UI 不可以直接呼叫 controller 的方法（必須靠 signal）

---

## Lv3 結尾：你真正學到的是什麼？

你學到的不是「connect 語法」，你學到的是 Qt 的工程哲學：

- **事件（signal）是廣播**
- **反應（slot）是訂閱者**
- **可多人監聽 = 可擴充**
- **低耦合 = 程式能活很久**

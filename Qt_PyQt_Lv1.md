# Lv1｜Qt / PyQt 基本結構：Event Loop 才是 GUI 的「主控台」

Lv1只做一件事：把你的心智模型從 **while(1)** 轉成 **GUI 的事件系統**。  
你不是在「控制流程」，你是在「回應事件」。

---

## 這一級要帶走的結論（先背起來）

1. **GUI 一定要有 `QApplication`**（它代表整個 GUI 執行環境）
2. **視窗要 `show()` 才會出現**
3. **真正的主迴圈在 `app.exec()`**（它就是 Qt 的事件迴圈）
4. **主執行緒不能阻塞**：不要 `sleep`、不要長 while、不要重運算塞在 slot 裡

---

## 一定要有 app 才能放 window 嗎？

**是的，基本上一定要有 `QApplication`**（或 `QGuiApplication` / `QCoreApplication`）。原因：

- Qt 的視窗、輸入事件、樣式、字型、平台整合都要依賴「Application 物件」
- 沒有 `QApplication`，你就沒有事件分派器（Event Dispatcher），也沒有 GUI 環境

你可以把 `QApplication` 想成：
- GUI 的「OS 介面層 + 事件中心 + 全域設定中心」

> 對照 MCU：`QApplication` 更像「整個系統 runtime」，不是一個普通物件。

---

## GUI ≠ main loop：差在哪？

### MCU
- 你掌控流程：`while(1){ read → compute → output }`
- 外部事件常用 ISR / flag / queue

### GUI（Qt）
- 外部事件很多：滑鼠、鍵盤、重繪、縮放、拖曳、定時、網路、序列埠…
- 你只負責寫「事件來了怎麼反應」
- Qt 在 `app.exec()` 內幫你跑主迴圈，並分派事件

> 你不是寫 while，你是寫 handler。

---

## 範例 1：最小可跑視窗（必背）

```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)

win = QWidget()
win.setWindowTitle("Hello Qt")
win.resize(420, 280)
win.show()

sys.exit(app.exec())
```

### 工程解釋
- `app.exec()`：開始處理事件（沒有它就不會有 UI 互動）
- `sys.exit(...)`：把 GUI 退出碼回傳給 OS（工程習慣）

---

## 範例 2：你以為的 while（錯誤示範）

```python
# ❌ 這樣寫會卡 UI：事件迴圈根本跑不到
while True:
    pass
```

### 為什麼會卡？
因為你把主執行緒佔滿了：
- Qt 沒機會處理重繪（paint）
- 沒機會處理滑鼠鍵盤事件
- 視窗會「未回應」

---

## 範例 3：按鈕點擊（事件回應入門）

```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel

app = QApplication(sys.argv)

win = QWidget()
label = QLabel("還沒點")
btn = QPushButton("點我")

def on_click():
    label.setText("我被點了！")

btn.clicked.connect(on_click)  # 事件 → 反應（slot）

layout = QVBoxLayout(win)
layout.addWidget(label)
layout.addWidget(btn)

win.show()
sys.exit(app.exec())
```

### 你要抓住的點
- `clicked` 是 **signal（事件）**
- `on_click` 是 **slot（反應）**
- 不是你「呼叫 clicked」，而是使用者點了，Qt 通知你

---

## 範例 4：用類別寫（工程上更常用）

```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Class-based UI")

        self.label = QLabel("0")
        self.btn = QPushButton("加 1")
        self.btn.clicked.connect(self.on_click)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.btn)

        self.count = 0

    def on_click(self):
        self.count += 1
        self.label.setText(str(self.count))

app = QApplication(sys.argv)
win = MainWindow()
win.show()
sys.exit(app.exec())
```

### 工程解釋
- UI 元件做成 `self.xxx`：後續更新狀態才好維護
- 狀態（count）與 UI（label）分開，但同一個 class 管也可以

---

## 範例 5：Override event（只示範概念）

你問過「為什麼 Qt 不讓你直接 override onclick？」  
事實上 Qt 可以 override 更底層事件（例如 mousePress），但一般應用層仍建議用 signal/slot。

```python
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QMouseEvent

class ClickArea(QWidget):
    def mousePressEvent(self, e: QMouseEvent):
        print("mouse pressed", e.position())
        super().mousePressEvent(e)
```

### 工程解釋
- override event 是「更底層」的操作（你要自己處理事件語意）
- signal/slot 是「更工程化」的封裝（可多人監聽、可解耦）

---

## Lv1 最重要：Non-blocking（主執行緒不能阻塞）

### 錯誤 1：sleep

```python
import time
time.sleep(2)   # ❌ UI 會凍結 2 秒
```

### 正確 1：QTimer.singleShot 做延遲

```python
from PyQt6.QtCore import QTimer

def later():
    print("2 秒後做事，但 UI 不會卡")

QTimer.singleShot(2000, later)
```

---

## 範例 6：用 QTimer 做週期性工作（Lv1 先會用法）

```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import QTimer
from datetime import datetime

class Clock(QWidget):
    def __init__(self):
        super().__init__()
        self.label = QLabel("...")
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

        self.timer = QTimer(self)
        self.timer.setInterval(200)            # 200ms 更新一次
        self.timer.timeout.connect(self.tick)  # timeout 事件
        self.timer.start()

    def tick(self):
        self.label.setText(datetime.now().strftime("%H:%M:%S.%f")[:-3])

app = QApplication(sys.argv)
w = Clock()
w.show()
sys.exit(app.exec())
```

### 工程解釋
- **週期性工作**應該交給事件系統（timer），不要手寫 while + sleep
- UI thread 仍然保持可回應

---

## 範例 7：長工作會卡 UI（先看錯誤，再看正解方向）

### 錯誤：slot 裡做大迴圈（UI 卡住）

```python
def on_click():
    s = 0
    for i in range(50_000_000):
        s += i
    label.setText(str(s))
```

你點下去那一刻：
- event loop 被你佔住
- 視窗不重繪、不回應

### 正解方向（先記住，Lv6 會完整教）
- **重運算放 thread**
- 算完用 signal 把結果送回 UI 更新畫面

---

## Lv1 常見錯誤清單（你只要避開就成功一半）

- 在主執行緒寫 `while True` 當主流程
- 用 `time.sleep()` 等待
- 在 slot/事件回呼裡做重運算或阻塞 I/O
- 視窗沒 `show()` 以為程式壞了
- 沒 `app.exec()` 就結束，視窗一閃就不見

---

## Lv1 小作業（真的做一次你就懂）

1. 做一個視窗，上面有：
   - 一個 Label（顯示數字）
   - 一個按鈕（每次按數字 +1）
2. 再加一個 QTimer：
   - 每 200ms 顯示現在時間（或顯示按鈕點擊次數）
3. **禁止使用 while/sleep**（只用事件）

---

## Lv1 你真正學到的是什麼？

你學到的不是「某個 API」，而是 GUI 的工程哲學：

- **Event loop 管流程**
- 你只寫「回應事件」
- **Non-blocking = 穩定的核心**

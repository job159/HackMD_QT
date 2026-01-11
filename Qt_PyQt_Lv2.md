# Lv2｜Widget 與 Layout：把 UI 做成「可維護工程」，不要做成「手刻座標地獄」

Lv1 你已經知道：Qt 的主控台是 `app.exec()` 事件迴圈，你只能寫事件回應。  
Lv2 你要把 UI 從「能跑」提升到「能活很久」：**元件選得對、排版做得對、邏輯拆得對**。

---

## Lv2 的教學意義（你在練什麼工程能力）

- 讓 UI 在不同解析度、DPI、字型、語系下仍然穩定（不跑版、不遮字）。
- 讓 UI 能改版（加一個欄位、換一排按鈕）不會整個爆掉。
- 讓 UI 可以重用：同一個小面板能塞到不同視窗、不同專案。
- 讓「顯示/輸入」跟「業務邏輯」分離：UI 壞了邏輯不壞、邏輯改了 UI 不需要重寫。

---

## 核心定錨（Lv2 先背）

1. **Widget 是畫面/輸入容器，不是邏輯中心**  
2. **Layout 是工程必需品：不要用 `move(x,y)` 手擺**  
3. **把 UI 拆成小 Widget，再組成大視窗**（避免巨石 MainWindow）

---

## 1) Widget 是什麼？（你在用的零件清單）

常用 Widget（工控/上位機最常見）：

- `QLabel`：文字/圖片顯示（狀態、標題）
- `QLineEdit`：單行輸入（IP、Port、參數）
- `QPlainTextEdit` / `QTextEdit`：log / 多行文字
- `QPushButton`：按鈕（Connect/Start/Stop）
- `QCheckBox`：開關（Enable/Disable）
- `QComboBox`：模式選擇（BaudRate、Device、Profile）
- `QSpinBox` / `QDoubleSpinBox`：數值設定（參數、閾值）
- `QSlider`：滑桿（速度、亮度）
- `QProgressBar`：進度（下載、燒錄）
- `QTableWidget` / `QTableView`：表格（設備列表、量測表）

> 你可以把 Widget 想成「面板上的元件」，**它負責顯示跟收輸入**。

---

## 2) 為什麼 Widget ≠ 邏輯？

如果把邏輯塞進 UI 會發生什麼：

- UI 改版 → 你要改一堆核心程式（高耦合）
- UI 變大 → MainWindow 變巨石（God Object），不好維護
- 測試困難 → 你只能靠「用手點」測，無法自動測
- 風險高 → 一個 UI 事件 bug 可能影響整個系統

**正確做法**：UI 只做兩件事：
1) 收使用者輸入（按鈕、輸入框、選單）  
2) 顯示狀態（label、表格、圖表）

業務邏輯（例如「連線協議」「設備狀態機」「參數驗證」「資料解析」）放到別的類別/模組。

---

## 3) Layout 的工程意義：為什麼不用手算座標？

### 手算座標你一定會爆的原因
- 解析度不同：1024×768 / 1920×1080 / 4K
- Windows DPI scaling：125% / 150%（常見）
- 字型大小或語系不同：中文字更寬
- 內容變長：狀態文字、檔名、路徑

你手算的 `move(120, 35)` 在別台機器可能直接跑版。

### Layout 幫你做什麼？
- 自動排版、對齊
- 自動伸縮（視窗拉大/縮小）
- 自動分配空間（誰該變大、誰固定大小）

---

# 範例區（Lv2 重點：範例要多）

下面全部以 **PyQt6** 為例（PyQt5 幾乎一樣）。

---

## 範例 1｜用 Layout 取代手算座標：垂直堆疊

```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout

app = QApplication(sys.argv)

win = QWidget()
win.setWindowTitle("VBoxLayout Demo")

title = QLabel("連線狀態：Disconnected")
btn = QPushButton("Connect")

layout = QVBoxLayout(win)       # ✅ 直接掛在 win 上
layout.addWidget(title)
layout.addWidget(btn)

win.resize(360, 160)
win.show()
sys.exit(app.exec())
```

**小解釋**
- `QVBoxLayout(win)`：layout 會自動管理 win 裡所有元件的尺寸與位置
- 你不用管座標，只管「順序」

---

## 範例 2｜水平排列 + 靠右對齊（工控常用）

```python
from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout

row = QHBoxLayout()
row.addStretch(1)              # ✅ 左邊留彈性空間 → 右對齊
row.addWidget(QPushButton("Start"))
row.addWidget(QPushButton("Stop"))
```

**小解釋**
- `addStretch(1)` 就像「彈簧」，把後面的按鈕推到右邊
- 這比 `move(x,y)` 穩定太多

---

## 範例 3｜QFormLayout：參數面板最乾淨的寫法

```python
from PyQt6.QtWidgets import QWidget, QLabel, QLineEdit, QFormLayout

panel = QWidget()
form = QFormLayout(panel)

ip = QLineEdit("192.168.1.10")
port = QLineEdit("502")

form.addRow(QLabel("IP"), ip)
form.addRow(QLabel("Port"), port)
```

**小解釋**
- 工控 UI 90% 都是這種「左 label / 右輸入」
- 你不用手動對齊，FormLayout 自己處理

---

## 範例 4｜QGridLayout：儀表/按鍵盤/控制區

```python
from PyQt6.QtWidgets import QWidget, QPushButton, QGridLayout

panel = QWidget()
grid = QGridLayout(panel)

keys = [
    ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
    ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
    ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
    ("0", 3, 1)
]

for text, r, c in keys:
    grid.addWidget(QPushButton(text), r, c)
```

**小解釋**
- `row/col` 排列很直覺
- 適合做控制按鈕區、儀表排列、測試面板

---

## 範例 5｜把 UI 拆成「可重用小 Widget」（工程做法）

你不要把所有元件塞在 MainWindow。拆成小部件：

```python
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtCore import pyqtSignal

class StatusPanel(QWidget):
    # ✅ 這個面板只負責顯示與輸入，不做連線邏輯
    connect_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.label = QLabel("Disconnected")
        self.btn = QPushButton("Connect")

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.btn)

        self.btn.clicked.connect(self.connect_requested.emit)

    def set_status(self, text: str):
        self.label.setText(text)
```

**小解釋**
- `StatusPanel` 是可重用零件：你之後換到另一個專案也能用
- 面板透過 `connect_requested` 發事件出去，不直接碰網路/串口

---

## 範例 6｜組裝大視窗（把小 Widget 拼起來）

```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPlainTextEdit
from PyQt6.QtCore import QObject

class Controller(QObject):
    # 這裡示範：控制層（以後可換成真 TCP/Serial driver）
    def __init__(self, ui_panel, log):
        super().__init__()
        self.ui_panel = ui_panel
        self.log = log
        ui_panel.connect_requested.connect(self.on_connect)

    def on_connect(self):
        self.log.appendPlainText("Connect requested")
        self.ui_panel.set_status("Connecting... (fake)")
        # 真實專案：這裡啟動 driver 連線、做狀態機

app = QApplication(sys.argv)

from PyQt6.QtWidgets import QWidget
root = QWidget()
layout = QVBoxLayout(root)

panel = StatusPanel()
log = QPlainTextEdit()
log.setReadOnly(True)

layout.addWidget(panel)
layout.addWidget(log)

ctrl = Controller(panel, log)

root.resize(420, 300)
root.show()
sys.exit(app.exec())
```

**小解釋**
- UI（Panel）只負責顯示/輸入
- Controller 負責流程（連線/狀態）
- 你一旦養成這種拆法，UI 就很好維護

---

## 範例 7｜QStackedWidget：多頁面（工控設定頁很常見）

```python
from PyQt6.QtWidgets import QWidget, QStackedWidget, QPushButton, QHBoxLayout, QVBoxLayout, QLabel

root = QWidget()

pages = QStackedWidget()
pages.addWidget(QLabel("主頁：狀態 / 控制"))
pages.addWidget(QLabel("設定頁：參數 / 通訊"))
pages.addWidget(QLabel("診斷頁：Log / 版本"))

btn_main = QPushButton("主頁")
btn_cfg  = QPushButton("設定")
btn_diag = QPushButton("診斷")

btn_main.clicked.connect(lambda: pages.setCurrentIndex(0))
btn_cfg.clicked.connect(lambda: pages.setCurrentIndex(1))
btn_diag.clicked.connect(lambda: pages.setCurrentIndex(2))

top = QHBoxLayout()
top.addWidget(btn_main)
top.addWidget(btn_cfg)
top.addWidget(btn_diag)
top.addStretch(1)

layout = QVBoxLayout(root)
layout.addLayout(top)
layout.addWidget(pages)
```

**小解釋**
- 一個視窗多頁面，不用開一堆子視窗
- 工控上位機很常：Main / Config / Diagnostics

---

## 範例 8｜表格：設備列表（上位機常用）

最簡單用 `QTableWidget`：

```python
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

table = QTableWidget(0, 3)
table.setHorizontalHeaderLabels(["ID", "IP", "Status"])

def add_device(dev_id, ip, status):
    r = table.rowCount()
    table.insertRow(r)
    table.setItem(r, 0, QTableWidgetItem(str(dev_id)))
    table.setItem(r, 1, QTableWidgetItem(ip))
    table.setItem(r, 2, QTableWidgetItem(status))

add_device(1, "192.168.1.10", "OK")
add_device(2, "192.168.1.11", "Timeout")
```

**小解釋**
- 小型專案 QTableWidget 最快
- 大型專案改用 Model/View（`QTableView + QAbstractTableModel`）更專業（以後再升級）

---

## Lv2 常見錯誤（你只要避開就很強）

- 不用 Layout，全部用 `move()` / `resize()` 手擺
- 把整個 UI + 協議 + 狀態機都塞在 `MainWindow`
- UI 直接操作硬體 / 網路（error 一來整個 UI 一起死）
- 元件寫成區域變數（後續要更新找不到）

---

## Lv2 範例建議

做一個「連線工具 UI」：

- 上方：`QFormLayout`（IP、Port、BaudRate 下拉）
- 中間：狀態 `QLabel`（Disconnected/Connecting/Connected）
- 下方：按鈕列（Connect / Disconnect / Clear log）右對齊
- 最下面：`QPlainTextEdit` 當 log 區

**要求**
- 全部用 Layout，不准 move()
- UI 拆成至少 2 個小 Widget（例如 ConnectionPanel + LogPanel）

---

## Lv2 結尾：你真正學到的是什麼？

你學到的不是「Widget 名稱」，而是 UI 工程化的 3 個習慣：

1. **用 Layout 取代座標**
2. **拆小 Widget 再組裝**
3. **UI 只做顯示/輸入，邏輯放控制層**

# Qt / PyQt 實戰（10 單元）— 單元 2：熟悉常用元件（以 PyQt6 為主）

> 目標：**不用先懂架構也沒關係**，先把「上位機最常見的元件」摸熟。  
> 這單元就是：**元件是什麼、什麼時候用、最常用的 API、最常踩的坑、最小可跑範例**。  
> （下一單元才會把 I/O、Thread、Model/View 拉進來。）

---

## 0) PyQt6 很重要的一句：很多類別不在 QtWidgets

你前面踩到的坑，本質是「類別在哪個 module」：

- `QAction`、`QShortcut` → **PyQt6.QtGui**
- 大部分 UI 元件（Button/LineEdit/ListWidget…）→ **PyQt6.QtWidgets**
- 計時器、正則、時間、訊號/槽、Thread… → **PyQt6.QtCore**

最小確認：

```python
from PyQt6.QtGui import QAction, QShortcut
from PyQt6.QtWidgets import QListWidget, QTreeWidget
from PyQt6.QtCore import QTimer
```

---

# 1) 本單元要熟悉的元件清單（超常用）

### A. 清單/樹狀/多頁
- `QListWidget`：事件/告警/歷史列表（最常見、最快上手）
- `QTreeWidget`：分群資料（產線→設備→點位）
- `QStackedWidget`：**同一區域切換不同頁**（比 Tab 更像產品）
- `QTabWidget`：多頁分頁（Console/Monitor/Config）

### B. 可調參數與狀態呈現
- `QSlider`：門檻、亮度、速度
- `QDial`：旋鈕（工控 UI 很常見）
- `QProgressBar`：進度/負載/佔用率
- `QLCDNumber`：大字數值看板（超像儀表）

### C. 「很像上位機/IDE」的結構件
- `QDockWidget`：可停靠工具窗（右側告警、左側裝置列表）
- `QScrollArea`：參數很多時（避免視窗爆長）
- `QToolBox`：像抽屜的分組面板
- `QSplitter`：可拖拉區塊（單元 1 用過，這裡補更實用技巧）

### D. 常用對話框與選擇器
- `QFileDialog`：開檔/存檔/選資料夾
- `QColorDialog`：狀態顏色（綠/黃/紅）
- `QFontDialog`：字型放大（看板）

---

# 2) 每個元件：何時用 + 常用 API + 最小可跑範例

> 你可以每個小節「複製貼上」跑一次。  
> 範例都用 PyQt6，且都可獨立跑。

---

## 2.1 QListWidget（事件/告警列表最常用）

### 什麼時候用？
- 你要快速做出「列表」：Log 檔名、告警、事件、設備簡單列表 → 用它最快。

### 常用 API
- `addItem(text)` / `addItems(list_of_text)`
- `insertItem(row, text)`：插入到最上面（告警常用）
- `currentRowChanged` / `itemClicked`：選到哪一項
- `takeItem(row)`：移除

### 最小可跑範例：點一下就把內容顯示到右邊 Label
```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QListWidget, QLabel

app = QApplication(sys.argv)
w = QWidget()
row = QHBoxLayout(w)

lst = QListWidget()
lst.addItems(["INFO Boot OK", "WARN Lost packet", "ALARM OverTemp"])
lbl = QLabel("點左邊一筆看看")
row.addWidget(lst)
row.addWidget(lbl)

def on_click(item):
    lbl.setText(f"你點到：{item.text()}")

lst.itemClicked.connect(on_click)

w.resize(600, 250)
w.show()
sys.exit(app.exec())
```

### 常踩坑
- **大量資料（幾萬筆）**不要用 QListWidget（之後單元 6 用 `QTableView + Model`）。
- 事件列表常見需求：**限行數**（保留最近 2000 行）避免跑久卡死。

---

## 2.2 QTreeWidget（分群資料：Line → Device → Point）

### 什麼時候用？
- 左側樹狀導航：工廠/產線/設備/測點，非常典型。

### 常用 API
- `setHeaderLabels(["Name","Status"])`
- `QTreeWidgetItem([col0, col1, ...])`
- `itemClicked`：點擊事件
- `setExpanded(True)`：預展開
- `item.parent()`：判斷是不是葉節點（真正設備）

### 最小可跑範例：點到 Device 才算選到設備
```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel

app = QApplication(sys.argv)
w = QWidget()
row = QHBoxLayout(w)

tree = QTreeWidget()
tree.setHeaderLabels(["Group/Device", "Status"])
lbl = QLabel("點一個 Device")

for line in ["Line1", "Line2"]:
    parent = QTreeWidgetItem([line, "OK"])
    tree.addTopLevelItem(parent)
    for dev in ["DeviceA", "DeviceB", "DeviceC"]:
        parent.addChild(QTreeWidgetItem([dev, "OK"]))
    parent.setExpanded(True)

def on_click(item, _col):
    if item.parent() is None:
        lbl.setText(f"你點到 group：{item.text(0)}（不是設備）")
        return
    lbl.setText(f"選到設備：{item.parent().text(0)} / {item.text(0)}")

tree.itemClicked.connect(on_click)

row.addWidget(tree, 2)
row.addWidget(lbl, 3)

w.resize(700, 320)
w.show()
sys.exit(app.exec())
```

### 常踩坑
- Tree 顯示很多欄位時，建議固定欄寬：`tree.setColumnWidth(0, 180)`  
- 你若要「資料/顯示分離」：後面會走 `QTreeView + Model`（先別急）。

---

## 2.3 QStackedWidget（同一區域切不同頁：比 Tab 更像產品）

### 什麼時候用？
- 「左邊選設備 → 中間切到設備詳情頁」這種 UI，非常適合 `QStackedWidget`。

### 常用 API
- `addWidget(page)`
- `setCurrentIndex(i)` / `setCurrentWidget(page)`

### 最小可跑範例：用按鈕切頁
```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QStackedWidget

app = QApplication(sys.argv)
w = QWidget()
layout = QVBoxLayout(w)

stack = QStackedWidget()

page1 = QLabel("Page 1：Overview")
page1.setStyleSheet("font-size:18px; font-weight:700;")
page2 = QLabel("Page 2：Detail")
page2.setStyleSheet("font-size:18px; font-weight:700;")

stack.addWidget(page1)
stack.addWidget(page2)

btn1 = QPushButton("切到 Overview")
btn2 = QPushButton("切到 Detail")

btn1.clicked.connect(lambda: stack.setCurrentIndex(0))
btn2.clicked.connect(lambda: stack.setCurrentIndex(1))

layout.addWidget(stack)
layout.addWidget(btn1)
layout.addWidget(btn2)

w.resize(520, 260)
w.show()
sys.exit(app.exec())
```

### 常踩坑
- 你不要把「很多不同功能」硬塞同一個頁面：用 Stack 分頁更乾淨。
- 之後單元 8 會加「記住上次停在哪頁」（`QSettings`）。

---

## 2.4 QDockWidget（可停靠工具窗：很像 IDE/SCADA）

### 什麼時候用？
- 右側告警列表、左側設備列表、下方 console → 都可以做成 dock。

### 常用 API
- `dock = QDockWidget("Title", self)`
- `dock.setWidget(widget)`
- `addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)`
- `setAllowedAreas(...)`：限制可停靠區域

### 最小可跑範例：右側停靠告警列表
```python
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QDockWidget, QListWidget

class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dock demo")
        self.setCentralWidget(QTextEdit("中央區域：顯示資料/圖表/console 都可"))

        dock = QDockWidget("Alarms", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        lst = QListWidget()
        lst.addItems(["INFO Boot OK", "ALARM OverTemp", "WARN Low voltage"])
        dock.setWidget(lst)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

app = QApplication(sys.argv)
win = Win()
win.resize(800, 500)
win.show()
sys.exit(app.exec())
```

### 常踩坑
- 不要把所有東西都放中央：Dock 會讓畫面更像專業工具。
- Dock 的可見性通常要綁 Menu 的 View（單元 1 你已經有 menu 的概念）。

---

## 2.5 QSlider / QDial / QProgressBar（調參 + 狀態）

### 什麼時候用？
- Slider：門檻/亮度/速度（線性）
- Dial：旋鈕（工控風格）
- Progress：CPU、電池、任務進度

### 常用 API
- `setRange(min, max)`
- `valueChanged.connect(handler)`
- Progress：`setValue(v)`

### 最小可跑範例：Slider 同步 Dial，同時控制 Progress
```python
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSlider, QDial, QProgressBar

app = QApplication(sys.argv)
w = QWidget()
layout = QVBoxLayout(w)

lbl = QLabel("Threshold: 30")
pb = QProgressBar(); pb.setRange(0, 100); pb.setValue(30)

slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(0, 100); slider.setValue(30)
dial = QDial(); dial.setRange(0, 100); dial.setValue(30)

def on_change(v: int):
    slider.setValue(v)
    dial.setValue(v)
    pb.setValue(v)
    lbl.setText(f"Threshold: {v}")
    lbl.setStyleSheet("font-weight:700; color:red;" if v > 80 else "font-weight:600;")

slider.valueChanged.connect(on_change)
dial.valueChanged.connect(on_change)

layout.addWidget(lbl)
layout.addWidget(pb)
layout.addWidget(slider)
layout.addWidget(dial)

w.resize(520, 320)
w.show()
sys.exit(app.exec())
```

### 常踩坑
- 如果你在 `valueChanged` 裡面互相 setValue：**只要值相同 Qt 不會反覆觸發**，所以通常不會死循環；但你做更複雜映射時要小心。

---

## 2.6 QLCDNumber（大字儀表）

### 什麼時候用？
- 顯示「大字數值」：RPM、溫度、電壓（非常像儀表板）

### 最小可跑範例：每秒 +1
```python
import sys
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLCDNumber

app = QApplication(sys.argv)
w = QWidget()
layout = QVBoxLayout(w)

lcd = QLCDNumber()
lcd.setDigitCount(6)
layout.addWidget(lcd)

value = {"v": 0}
def tick():
    value["v"] += 1
    lcd.display(value["v"])

t = QTimer()
t.timeout.connect(tick)
t.start(1000)

w.resize(260, 160)
w.show()
sys.exit(app.exec())
```

---

## 2.7 QScrollArea（參數很多時「一定要有」）

### 什麼時候用？
- 你有一個超長參數表單（50~200 個欄位），沒 ScrollArea 會爆版。

### 核心概念
- ScrollArea 裡面放「一個 container widget」，container 裡面再放 layout。

### 最小骨架（你可把一堆 GroupBox 塞進去）
```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QScrollArea, QLabel

app = QApplication(sys.argv)
w = QWidget()
root = QVBoxLayout(w)

scroll = QScrollArea()
scroll.setWidgetResizable(True)

container = QWidget()
v = QVBoxLayout(container)
for i in range(50):
    v.addWidget(QLabel(f"Param {i}"))

scroll.setWidget(container)
root.addWidget(scroll)

w.resize(400, 350)
w.show()
sys.exit(app.exec())
```

---

## 2.8 常用 Dialog：File / Color / Font（產品必備）

### `QFileDialog`
- `getOpenFileName()` / `getSaveFileName()` / `getExistingDirectory()`

### `QColorDialog`
- `c = QColorDialog.getColor()` → `c.isValid()` → `c.name()`

### `QFontDialog`
- `ok, font = QFontDialog.getFont()`（注意回傳順序）

（單元 1 你已經用過 QMessageBox；這單元就把上面三個熟一下就好。）

---

# 3) 小練習（真的會進步，且不難）

> 你做完這 5 個練習，單元 3 接 I/O 會非常順。

1. 用 `QListWidget` 做「告警列表」：按鈕一按就 `insertItem(0, ...)`，並限制最多 200 筆。
2. 用 `QTreeWidget` 做「Line/Device」：點 Device 才更新右側 Label。
3. 用 `QStackedWidget` 做兩頁：Overview / Detail；Tree 點 Device 就切到 Detail。
4. 用 `QDockWidget` 做右側「Events」窗：可關閉/可停靠左右。
5. Slider 控制「門檻」，門檻 > 80 時把 Label 變紅。

---

# 4) 下一單元（單元 3）會做什麼？

把你已經熟悉的 UI 元件接到「真的能用的 I/O 監看器」：

- `readyRead` + buffer + framing（TCP / Serial）
- 「連線/斷線/重連/超時」流程清楚
- UI 不會卡（thread / timer / queue）

但在那之前，**單元 2 先把元件手感練起來**就對了。

---

# 5) 完整版 Demo（把本講義提到的元件一次串起來）

> ✅ **你要的「完整版」在這裡**：把本講義提到的元件都放進同一個可跑 App。  
> 上面講義內容**完全不改**，只是在最下面加這個完整版。  
>
> 你會看到：
> - 左側 `QTreeWidget`：Line/Device
> - 中央 `QStackedWidget`：Overview / Detail（每頁裡用 `QTabWidget`）
> - 右側 `QDockWidget + QListWidget`：Events/Alarms
> - 下方 `QSplitter`：可拖拉比例
> - Overview：`QSlider + QDial + QProgressBar + QLCDNumber`（全部連動）
> - Detail：一個超長參數區 → `QScrollArea`；並用 `QToolBox` 做「抽屜式」分類
> - Toolbar：`QFileDialog / QColorDialog / QFontDialog`（實戰必備）
> - 另外加：`QShortcut`（Ctrl+L 清事件、Ctrl+K 加告警）與 `QAction`

把下面存成 `unit02_full_demo.py` 執行：

```bash
pip install PyQt6
python unit02_full_demo.py
```

```python
import sys
from PyQt6.QtCore import Qt, QDateTime, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit,
    QListWidget, QTreeWidget, QTreeWidgetItem,
    QStackedWidget, QTabWidget,
    QSlider, QDial, QProgressBar, QLCDNumber,
    QDockWidget, QScrollArea, QToolBox, QSplitter,
    QDateTimeEdit, QFileDialog, QColorDialog, QFontDialog,
    QMessageBox, QToolBar, QGroupBox
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unit02 FULL - Common Widgets (PyQt6)")
        self.resize(1200, 760)

        self._build_toolbar()
        self._build_shortcuts()

        # ===== 中央：Splitter（左 tree / 中央 pages） =====
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(self.main_splitter, 1)

        # ---- left: tree ----
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Group/Device", "Status"])
        self.tree.setColumnWidth(0, 180)
        self._fill_tree()
        self.tree.itemClicked.connect(self.on_tree_clicked)
        self.main_splitter.addWidget(self.tree)

        # ---- middle: stacked pages ----
        self.stack = QStackedWidget()
        self.main_splitter.addWidget(self.stack)

        self.page_overview = self._build_page_overview()
        self.page_detail = self._build_page_detail()
        self.stack.addWidget(self.page_overview)
        self.stack.addWidget(self.page_detail)

        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([320, 780])

        # ===== 右側 Dock：Events/Alarms =====
        self._build_dock_events()

        # 初始選擇
        self._set_selected_device("Line1 / DeviceA")
        self.stack.setCurrentWidget(self.page_overview)

        # 小心跳：示範 QTimer 更新時間/假資料
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    # ---------------- toolbar / shortcuts ----------------
    def _build_toolbar(self):
        tb = QToolBar("Tools")
        self.addToolBar(tb)

        act_open = QAction("Open...", self)
        act_save = QAction("Save...", self)
        act_color = QAction("Color...", self)
        act_font = QAction("Font...", self)
        act_about = QAction("About", self)

        act_open.triggered.connect(self.open_file)
        act_save.triggered.connect(self.save_file)
        act_color.triggered.connect(self.pick_color)
        act_font.triggered.connect(self.pick_font)
        act_about.triggered.connect(self.about)

        tb.addAction(act_open)
        tb.addAction(act_save)
        tb.addSeparator()
        tb.addAction(act_color)
        tb.addAction(act_font)
        tb.addSeparator()
        tb.addAction(act_about)

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.clear_events)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.add_alarm)

    # ---------------- left tree ----------------
    def _fill_tree(self):
        for line in ["Line1", "Line2"]:
            parent = QTreeWidgetItem([line, "OK"])
            self.tree.addTopLevelItem(parent)
            for dev in ["DeviceA", "DeviceB", "DeviceC"]:
                parent.addChild(QTreeWidgetItem([dev, "OK"]))
            parent.setExpanded(True)

    def on_tree_clicked(self, item: QTreeWidgetItem, _col: int):
        if item.parent() is None:
            # 點到 group
            self.add_event(f"INFO  click group: {item.text(0)}")
            self.stack.setCurrentWidget(self.page_overview)
            return

        group = item.parent().text(0)
        dev = item.text(0)
        self._set_selected_device(f"{group} / {dev}")
        self.stack.setCurrentWidget(self.page_detail)
        self.add_event(f"INFO  select device: {group}/{dev}")

    # ---------------- dock events ----------------
    def _build_dock_events(self):
        dock = QDockWidget("Events / Alarms (QListWidget)", self)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )

        self.list_events = QListWidget()
        self.list_events.addItems([
            "INFO  Boot OK",
            "WARN  Packet lost (fake)",
            "ALARM OverTemp (fake)",
        ])
        dock.setWidget(self.list_events)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def add_event(self, text: str):
        # 常見工程實戰：限制筆數避免跑一晚卡死
        MAX_ITEMS = 300
        self.list_events.insertItem(0, text)
        while self.list_events.count() > MAX_ITEMS:
            self.list_events.takeItem(self.list_events.count() - 1)

    def clear_events(self):
        self.list_events.clear()
        self.add_event("SYS  events cleared (Ctrl+L)")

    def add_alarm(self):
        self.add_event("ALARM OverTemp (fake) (Ctrl+K)")
        QMessageBox.warning(self, "Alarm", "OverTemp (fake)")

    # ---------------- overview page ----------------
    def _build_page_overview(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)

        self.lbl_title = QLabel("Overview")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: 800;")
        v.addWidget(self.lbl_title)

        # Overview 內用 TabWidget（常見：總覽/圖表/console）
        tabs = QTabWidget()
        v.addWidget(tabs, 1)

        # ---- Tab 1: Monitor ----
        tab_mon = QWidget()
        g = QGridLayout(tab_mon)

        # DateTimeEdit
        g.addWidget(QLabel("Timestamp (QDateTimeEdit)"), 0, 0)
        self.dt = QDateTimeEdit()
        self.dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.dt.setDateTime(QDateTime.currentDateTime())
        g.addWidget(self.dt, 0, 1)

        btn_now = QPushButton("Now")
        btn_now.clicked.connect(lambda: self.dt.setDateTime(QDateTime.currentDateTime()))
        g.addWidget(btn_now, 0, 2)

        # Slider / Dial / Progress / LCD
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(30)

        self.dial = QDial()
        self.dial.setRange(0, 100)
        self.dial.setValue(30)

        self.pb = QProgressBar()
        self.pb.setRange(0, 100)
        self.pb.setValue(30)

        self.lcd = QLCDNumber()
        self.lcd.setDigitCount(3)
        self.lcd.display(30)

        self.lbl_threshold = QLabel("Threshold: 30")
        self.lbl_threshold.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.slider.valueChanged.connect(self.on_threshold_changed)
        self.dial.valueChanged.connect(self.on_threshold_changed)

        g.addWidget(QLabel("QProgressBar"), 1, 0)
        g.addWidget(self.pb, 1, 1, 1, 2)

        g.addWidget(QLabel("QSlider"), 2, 0)
        g.addWidget(self.slider, 2, 1, 1, 2)

        g.addWidget(QLabel("QDial"), 3, 0)
        g.addWidget(self.dial, 3, 1)
        g.addWidget(self.lcd, 3, 2)

        g.addWidget(self.lbl_threshold, 4, 0, 1, 3)

        tabs.addTab(tab_mon, "Monitor")

        # ---- Tab 2: Quick actions ----
        tab_quick = QWidget()
        qv = QVBoxLayout(tab_quick)
        btn_go_detail = QPushButton("Go Device Detail (StackedWidget)")
        btn_go_detail.clicked.connect(lambda: self.stack.setCurrentWidget(self.page_detail))
        qv.addWidget(btn_go_detail)

        btn_add_info = QPushButton("Add INFO event")
        btn_add_info.clicked.connect(lambda: self.add_event("INFO  user clicked Add INFO"))
        qv.addWidget(btn_add_info)

        qv.addStretch(1)
        tabs.addTab(tab_quick, "Quick")

        return w

    def on_threshold_changed(self, v: int):
        # 連動
        self.slider.setValue(v)
        self.dial.setValue(v)
        self.pb.setValue(v)
        self.lcd.display(v)
        self.lbl_threshold.setText(f"Threshold: {v}")

        if v > 80:
            self.lbl_threshold.setStyleSheet("font-weight: 800; color: red;")
        else:
            self.lbl_threshold.setStyleSheet("font-weight: 600;")

        if v in (50, 80, 90):
            self.add_event(f"WARN  threshold changed: {v}")

    # ---------------- detail page ----------------
    def _build_page_detail(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)

        self.lbl_dev = QLabel("Device Detail")
        self.lbl_dev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_dev.setStyleSheet("font-size: 18px; font-weight: 800;")
        v.addWidget(self.lbl_dev)

        # Detail 內也用 Tab：Info / Params
        tabs = QTabWidget()
        v.addWidget(tabs, 1)

        # ---- Tab: Info ----
        tab_info = QWidget()
        fv = QFormLayout(tab_info)
        self.edit_name = QLineEdit("DeviceA")
        self.edit_ip = QLineEdit("192.168.1.10")
        fv.addRow("Name", self.edit_name)
        fv.addRow("IP", self.edit_ip)
        tabs.addTab(tab_info, "Info")

        # ---- Tab: Params（ScrollArea + ToolBox）----
        tab_params = QWidget()
        pv = QVBoxLayout(tab_params)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        pv.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        cv = QVBoxLayout(container)

        toolbox = QToolBox()
        cv.addWidget(toolbox)

        # Drawer 1
        box1 = QWidget()
        box1_l = QFormLayout(box1)
        for i in range(20):
            box1_l.addRow(f"Param A{i}", QLineEdit(str(i)))
        toolbox.addItem(box1, "Group A (QToolBox)")

        # Drawer 2
        box2 = QWidget()
        box2_l = QFormLayout(box2)
        for i in range(20):
            box2_l.addRow(f"Param B{i}", QLineEdit(str(i * 10)))
        toolbox.addItem(box2, "Group B (QToolBox)")

        # Drawer 3：GroupBox inside scroll
        gb = QGroupBox("Extra Params (GroupBox in ScrollArea)")
        gb_l = QFormLayout(gb)
        for i in range(15):
            gb_l.addRow(f"Extra {i}", QLineEdit("..."))
        cv.addWidget(gb)

        cv.addStretch(1)

        tabs.addTab(tab_params, "Params")

        # bottom buttons
        row = QHBoxLayout()
        btn_save = QPushButton("Save Params (fake)")
        btn_save.clicked.connect(lambda: self.add_event("INFO  save params (fake)"))
        btn_back = QPushButton("Back to Overview")
        btn_back.clicked.connect(lambda: self.stack.setCurrentWidget(self.page_overview))
        row.addWidget(btn_save)
        row.addWidget(btn_back)
        v.addLayout(row)

        return w

    # ---------------- misc ----------------
    def _set_selected_device(self, name: str):
        self.lbl_title.setText(f"Overview - {name}")
        self.lbl_dev.setText(f"Device Detail - {name}")
        self.edit_name.setText(name.split("/")[-1].strip())

    def _tick(self):
        # 每秒更新 timestamp
        self.dt.setDateTime(QDateTime.currentDateTime())

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*.*)")
        if path:
            self.add_event(f"INFO  open file: {path}")

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "output.txt", "Text Files (*.txt)")
        if path:
            self.add_event(f"INFO  save file: {path}")

    def pick_color(self):
        c = QColorDialog.getColor()
        if c.isValid():
            self.add_event(f"INFO  color: {c.name()}")
            # 直接拿來當狀態色（示範）
            self.lbl_dev.setStyleSheet(f"font-size:18px; font-weight:800; color:{c.name()};")

    def pick_font(self):
        ok, font = QFontDialog.getFont()
        if ok:
            self.add_event(f"INFO  font: {font.family()}")
            self.lbl_title.setFont(font)

    def about(self):
        QMessageBox.information(
            self,
            "About",
            "Unit02 FULL Demo\n"
            "- Tree / List / Dock / Stacked / Tabs\n"
            "- Slider / Dial / Progress / LCD\n"
            "- ScrollArea / ToolBox\n"
            "- File/Color/Font Dialog\n"
            "- Ctrl+L clear events, Ctrl+K alarm"
        )


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

---

## 你用這份完整版的建議練法（很快就熟）

1. **先不改任何程式**：只跑起來、點 tree、拖 splitter、開關 dock、調 slider。
2. 改一件事：把 `MAX_ITEMS` 改成 50，看看事件列表怎麼被截斷。
3. 改一件事：把 threshold > 80 的紅色判斷改成 > 60。
4. 改一件事：在 `on_tree_clicked` 讓點到 Device 時，把 status 欄位改成 `BUSY`（提示：`item.setText(1, "BUSY")`）。
5. 做到上面 4 個，你就可以進單元 3 接真 I/O 了。


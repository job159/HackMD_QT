# Lv7｜工程化進階：Model/View、狀態機、設定保存、部署打包（工控上位機開始「像產品」）

Lv1～Lv6 你已經把「不卡」做到了：事件迴圈、Signal/Slot、QTimer、I/O、Thread 都到位。  
Lv7 開始要把專案做成「可擴充、可維護、可交付」的工程品，尤其是工控/上位機最常缺的這幾塊：

- **資料量一大就爆的 UI** → 用 **Model/View**
- **流程一複雜就亂的程式** → 用 **狀態機 State Machine**
- **每次開程式都要重設** → 用 **QSettings**
- **要交給別人用（Windows 打包）** → 用 **部署/打包策略**
- **要能追 bug** → 用 **Log + 例外處理 + UI 節流**

---

## Lv7 先背 5 個定錨（這級的核心）

1. **表格/列表不要一直 `setItem` 暴力刷新** → 用 **QAbstractTableModel**
2. **流程不要寫成一堆 if/else** → 用 **QStateMachine（或明確的 FSM）**
3. **設定（IP/Port/視窗大小）要自動保存** → 用 **QSettings**
4. **大量資料進 UI 要節流**（Lv6 的 batch refresh 延伸）
5. **要能打包交付**：資源、依賴、路徑、log、崩潰回報要一併設計

---

# Part A｜Model/View：表格資料一多還能穩的「正解」

## 為什麼要 Model/View？
你如果用 `QTableWidget`：
- 小專案很快，但資料量大、頻繁更新時會卡
- UI 邏輯和資料耦在一起，難做排序/過濾/搜尋

Model/View 的精神：
- **Model 管資料（真相來源）**
- View 只是顯示（table view）
- 更新資料時，通知 view 哪裡改了（最小刷新）

---

## 範例 1｜最小 QAbstractTableModel（可直接用在工控設備列表）

```python
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex

class DeviceModel(QAbstractTableModel):
    def __init__(self, rows=None):
        super().__init__()
        self.headers = ["ID", "IP", "Status", "RSSI"]
        self.rows = rows or []  # list of dict 或 list of list 都行

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return str(section)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        row = self.rows[index.row()]
        col = index.column()

        if col == 0: return str(row["id"])
        if col == 1: return row["ip"]
        if col == 2: return row["status"]
        if col == 3: return str(row["rssi"])
        return None
```

### View 端使用：

```python
from PyQt6.QtWidgets import QTableView

model = DeviceModel([
    {"id": 1, "ip": "192.168.1.10", "status": "OK", "rssi": -55},
    {"id": 2, "ip": "192.168.1.11", "status": "Timeout", "rssi": -99},
])

view = QTableView()
view.setModel(model)
```

---

## 範例 2｜更新某一格：只刷新需要的 cell（不卡的關鍵）

```python
from PyQt6.QtCore import QModelIndex

def update_status(model: DeviceModel, row_idx: int, new_status: str):
    model.rows[row_idx]["status"] = new_status

    col_status = 2
    top_left = model.index(row_idx, col_status)
    bottom_right = model.index(row_idx, col_status)

    # ✅ 通知 view：只有這格變了
    model.dataChanged.emit(top_left, bottom_right)
```

---

## 範例 3｜新增/刪除列（必用 begin/end）

```python
def add_device(model: DeviceModel, dev: dict):
    r = model.rowCount()
    model.beginInsertRows(QModelIndex(), r, r)
    model.rows.append(dev)
    model.endInsertRows()

def remove_device(model: DeviceModel, row_idx: int):
    model.beginRemoveRows(QModelIndex(), row_idx, row_idx)
    del model.rows[row_idx]
    model.endRemoveRows()
```

---

## 範例 4｜排序/搜尋（Proxy Model：工控 UI 常用）

```python
from PyQt6.QtCore import QSortFilterProxyModel

proxy = QSortFilterProxyModel()
proxy.setSourceModel(model)
proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
proxy.setFilterKeyColumn(1)    # 以 IP 欄搜尋

view.setModel(proxy)

# 例如：只顯示 IP 含 "192.168.1.1"
proxy.setFilterFixedString("192.168.1.1")

# 排序：點表頭即可（你也可以手動呼叫）
view.setSortingEnabled(True)
```

---

# Part B｜狀態機：工控/通訊流程別再一堆 if/else

你專案一旦有「連線→握手→登入→收資料→錯誤重連→恢復」  
如果全部寫在 if/else，很快就變成「誰也不敢改」的地獄。

## Qt 的選項：QStateMachine（或你自己寫 FSM）
Qt 有 `QStateMachine` / `QState` / `QFinalState`，適合做 UI 流程、連線流程。

---

## 範例 5｜最小 QStateMachine：Disconnected → Connecting → Connected

```python
from PyQt6.QtCore import QObject, QStateMachine, QState, pyqtSignal

class ConnFSM(QObject):
    sig_connect = pyqtSignal()
    sig_connected = pyqtSignal()
    sig_disconnect = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.m = QStateMachine()

        self.s_dis = QState()
        self.s_conning = QState()
        self.s_conned = QState()

        # 轉移
        self.s_dis.addTransition(self.sig_connect, self.s_conning)
        self.s_conning.addTransition(self.sig_connected, self.s_conned)
        self.s_conned.addTransition(self.sig_disconnect, self.s_dis)

        # 進入狀態時做什麼（建議：只更新 UI / 觸發動作）
        self.s_dis.entered.connect(lambda: print("STATE: Disconnected"))
        self.s_conning.entered.connect(lambda: print("STATE: Connecting"))
        self.s_conned.entered.connect(lambda: print("STATE: Connected"))

        self.m.addState(self.s_dis)
        self.m.addState(self.s_conning)
        self.m.addState(self.s_conned)
        self.m.setInitialState(self.s_dis)

        self.m.start()
```

### 工程使用方式（概念）
- UI 按下 Connect：`fsm.sig_connect.emit()`
- Driver 真的連上了：`fsm.sig_connected.emit()`
- 斷線或按 Disconnect：`fsm.sig_disconnect.emit()`

> 你會發現：流程變清楚了，錯誤處理也更好插。

---

# Part C｜QSettings：讓程式「記得上次設定」像產品

工控/上位機最常見要記：
- IP、Port、BaudRate
- 最後選的 COM port
- 視窗大小/位置
- 使用者偏好（顯示單位、語言、主題）

---

## 範例 6｜保存/讀取設定（IP/Port）

```python
from PyQt6.QtCore import QSettings

settings = QSettings("YourCompany", "YourApp")

# 讀
ip = settings.value("conn/ip", "192.168.1.10")
port = int(settings.value("conn/port", 502))

# 寫
settings.setValue("conn/ip", "192.168.1.20")
settings.setValue("conn/port", 1502)
```

---

## 範例 7｜保存視窗幾何（大小/位置）

```python
def load_window_state(win, settings):
    geo = settings.value("ui/geometry")
    if geo is not None:
        win.restoreGeometry(geo)

def save_window_state(win, settings):
    settings.setValue("ui/geometry", win.saveGeometry())
```

把 `save_window_state` 放在 `closeEvent` 內就行。

---

# Part D｜資源與 UI 組裝：Designer / .ui / Resource（實務常用）

## 你可以怎麼做 UI？
1. **純手寫 code（你現在 Lv1～Lv6 這樣）**：最可控、最清楚  
2. **Qt Designer 做 `.ui`**：快速做版型，工程上很常用  
3. **.qrc 資源**：把 icon、圖片、字型打包在程式內，不怕路徑問題

---

## 範例 8｜載入 .ui（快速做大 UI）

```python
from PyQt6 import uic
from PyQt6.QtWidgets import QMainWindow

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("main.ui", self)  # main.ui 由 Qt Designer 產生

        # 假設 ui 裡有一顆按鈕叫 btnConnect
        self.btnConnect.clicked.connect(self.on_connect)

    def on_connect(self):
        print("connect")
```

---

## 範例 9｜使用 Qt Resource（概念示例）
（PyQt 專案通常會用 pyrcc 把 .qrc 編成 python module）

```python
# 假設你已經把資源編成 resources_rc.py 並 import
import resources_rc
from PyQt6.QtGui import QIcon

btn.setIcon(QIcon(":/icons/connect.png"))
```

> 工程上好處：不怕「找不到 icon 路徑」造成崩潰。

---

# Part E｜部署打包（Windows 最常）：PyInstaller 方向（概念＋重點清單）

你問過「Windows 連 pytorch 也不能裝嗎？」這類問題很多時候不是 Qt 的問題，是：
- Python 版本 / 架構（x86/x64/ARM）
- wheel 是否有對應平台
- 編譯器/系統依賴

**但 Qt 上位機要交付時，通常你會打包成 exe。**

## 實務重點（你一定會遇到）
- Qt plugins（platforms、styles、imageformats）要被打包進去
- `.ui`、icons、config、dll 路徑要正確
- 記錄 log 到可寫路徑（`AppData` 或 exe 同層）

> 這裡不貼死命令（每個專案差太多），你要的核心是：**打包=資源+插件+路徑策略**。

---

# Part F｜Log 與錯誤處理：工控上位機沒 log 等於盲飛

## 範例 10｜Python logging + UI log 面板（常用）

```python
import logging
from PyQt6.QtCore import QObject, pyqtSignal

class QtLogHandler(logging.Handler, QObject):
    sig = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.sig.emit(msg)

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

qt_handler = QtLogHandler()
qt_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
logger.addHandler(qt_handler)

# UI：把 log handler 的 signal 接到 QPlainTextEdit
qt_handler.sig.connect(ui_log.appendPlainText)

logger.info("app started")
```

---

## 範例 11｜全域例外捕捉（避免直接閃退沒訊息）

```python
import sys, traceback

def except_hook(exctype, value, tb):
    msg = "".join(traceback.format_exception(exctype, value, tb))
    print(msg)  # 也可以寫到 log 檔
    # TODO: 顯示對話框或寫入 crash report

sys.excepthook = except_hook
```

---

# Lv7 常見錯誤（很多人做到 Lv6 還是會翻）

- 表格更新用 QTableWidget 一直全刷新 → 資料大就卡
- 流程用 if/else 堆成一座山 → 一改就出 bug
- 設定不保存 → 每次重開都要重設（使用者會爆炸）
- log 沒設計 → 出事找不到原因
- UI 更新太頻繁 → 即使 thread 做得好，UI 仍然被刷爆（要節流）

---

# Lv7 小作業（做完就像工控產品）

做一個「設備監控上位機」骨架：

1. 一個 `DeviceModel`（Model/View）顯示設備列表
2. 一個 `ConnFSM` 管理連線狀態（Disconnected/Connecting/Connected/Error）
3. `QSettings` 保存 IP/Port/視窗大小
4. 有 log 面板：使用 logging handler 把 log 顯示在 UI
5. 模擬設備資料更新：背景 thread 每秒更新某些設備 status/rssi（更新 model 的單格）

**要求**
- UI thread 不准卡
- 表格更新只改動的那格（dataChanged）
- 狀態切換全靠 signal（不要 if/else 大雜燴）

---

## Lv7 結尾：你真正學到的是什麼？

Lv7 不是「更多 API」，而是把專案升級成產品級的工程能力：

- **Model/View**：資料量大仍然穩
- **State Machine**：流程清楚可維護
- **QSettings**：使用體驗像產品
- **部署/資源/Log**：可交付、可追 bug

你如果要下一級（Lv8），通常就是：**多媒體（Qt Multimedia / OpenCV / GStreamer）、繪圖/圖表、插件化架構、單元測試與CI**。

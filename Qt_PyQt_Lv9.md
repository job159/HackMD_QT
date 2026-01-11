# Lv9｜可插拔架構與工程品質：Plugin、依賴反轉、測試/CI、Profiling、記憶體洩漏、可靠交付（真正產品級）

Lv8 你已經能做「影像/串流/圖表」並且不卡。  
Lv9 開始是你做工控/上位機 **最容易被忽略但最值錢** 的那一段：把專案做成「可以長期維護、可以多人協作、可以換硬體/換協議不重寫」的產品工程。

這級會把所有東西收斂成一句話：

> **把變動點（設備/協議/演算法/後端）做成可插拔插件，把核心（UI/流程/資料模型）做成穩定平台。**

---

## Lv9 先背 7 個定錨（這級的核心）

1. **依賴反轉（Dependency Inversion）**：UI/流程不依賴具體 Driver，只依賴介面（Protocol/ABC）
2. **Plugin 化**：Driver、Parser、Processor、Recorder 都是 plugin（可換、可新增）
3. **事件總線（Event Bus）/訊息模型**：統一資料流（signal/slot + dataclass）
4. **配置驅動（Config-driven）**：用設定決定載入哪個 plugin，而不是改 code
5. **測試優先**：Parser/FSM/Model 必須可單元測試（不靠 UI 點）
6. **可觀測性（Observability）**：logging、metrics、trace、crash report
7. **效能與資源**：profiling、backpressure、記憶體洩漏追查、打包一致化

---

# Part A｜依賴反轉：先把 Driver/Processor「抽象化」

## 1) 介面（interface）是什麼？（用 Python ABC 寫）

```python
from abc import ABC, abstractmethod

class ITransport(ABC):
    @abstractmethod
    def open(self) -> bool: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def write(self, data: bytes) -> None: ...

    # 事件：收到資料（你可以用 Qt signal 或 callback）
```

### 工程意義
- UI/Controller 不再依賴「TCP/Serial/USB」這些細節
- 你換成 Modbus、RS485、CAN，只要做一個新實作

---

## 2) 用 dataclass 統一「資料模型」（讓 UI/Log/DB 共享同一格式）

```python
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class Frame:
    ts_ms: int
    source: str                    # "tcp:192.168.1.10:502" / "com:COM3"
    kind: Literal["raw", "line", "packet"]
    payload: bytes
    note: Optional[str] = None
```

### 工程意義
- 你不用在不同模組傳來傳去一堆不一致的 dict
- 你能做 log、存檔、回放（replay）都更容易

---

# Part B｜Plugin 架構：Driver/Parser/Processor 都做成「可載入」

Qt 本身有 plugin 機制，但在 PyQt 專案常見做法是「Python plugin」：

- 每個 plugin 是一個 module（檔案）
- 透過 importlib 動態載入
- 透過一個 `create()` 工廠函數回傳實例

---

## 範例 1｜Plugin 協議：統一 create(config) 入口

### plugins/serial_transport.py

```python
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtSerialPort import QSerialPort

class SerialTransport(QObject):
    rx = pyqtSignal(bytes)

    def __init__(self, port: str, baud: int):
        super().__init__()
        self.ser = QSerialPort()
        self.ser.setPortName(port)
        self.ser.setBaudRate(baud)
        self.ser.readyRead.connect(self._on_ready)

    def open(self) -> bool:
        return self.ser.open(QSerialPort.OpenModeFlag.ReadWrite)

    def close(self) -> None:
        self.ser.close()

    def write(self, data: bytes) -> None:
        self.ser.write(data)

    def _on_ready(self):
        self.rx.emit(self.ser.readAll().data())

def create(config: dict) -> SerialTransport:
    return SerialTransport(config["port"], int(config["baud"]))
```

---

## 範例 2｜用 importlib 動態載入 plugin（核心平台）

```python
import importlib

def load_plugin(path: str, config: dict):
    # path 例："plugins.serial_transport"
    mod = importlib.import_module(path)
    return mod.create(config)
```

---

## 範例 3｜用 JSON/YAML 決定載入哪個 plugin（Config-driven）

config.json：

```json
{
  "transport": {
    "plugin": "plugins.serial_transport",
    "config": { "port": "COM3", "baud": 115200 }
  },
  "parser": {
    "plugin": "plugins.line_parser",
    "config": { "delimiter": "\n" }
  }
}
```

程式：

```python
import json

cfg = json.load(open("config.json", "r", encoding="utf-8"))

transport = load_plugin(cfg["transport"]["plugin"], cfg["transport"]["config"])
parser    = load_plugin(cfg["parser"]["plugin"], cfg["parser"]["config"])
```

### 工程意義
- 使用者/現場工程師改設定就能換協議或換設備
- 你不用重編、也不用改 UI

---

# Part C｜事件總線（Event Bus）：把 Signal/Slot 提升成「系統消息模型」

當模組多了，你會想要：
- UI 不用知道每個 driver 的 signal 名字
- 任何模組都能訂閱某一類事件（如 frame、state、alarm）

最簡化做法：一個 QObject 當事件中心。

---

## 範例 4｜最小 EventBus（Qt signal 版）

```python
from PyQt6.QtCore import QObject, pyqtSignal

class EventBus(QObject):
    frame = pyqtSignal(object)      # Frame
    state = pyqtSignal(str)         # "Connected" / "Error:..."
    alarm = pyqtSignal(str)         # "OverTemp" / "Timeout"
    log   = pyqtSignal(str)

bus = EventBus()
```

Driver → bus：

```python
transport.rx.connect(lambda raw: bus.frame.emit(raw))
```

任何模組訂閱：

```python
bus.log.connect(ui_log.appendPlainText)
bus.state.connect(lambda s: ui_status.setText(s))
```

### 工程意義
- 模組之間耦合大幅下降
- 你可以替換 driver / parser，而 UI 不用改連接線（只連 bus）

---

# Part D｜可測試：把核心邏輯從 Qt/UI 里抽出來

你想要能測：
- Parser：亂包/半包/雜訊是否解析正確
- FSM：各事件是否走對狀態
- Model：資料更新是否正確（rowCount/dataChanged）

關鍵：**把可測的核心寫成純 Python，不依賴 UI。**

---

## 範例 5｜Parser 單元測試（pytest 概念）

### 核心 parser（純 Python，不用 Qt）

```python
class LineFramer:
    def __init__(self, delim=b"\n"):
        self.buf = bytearray()
        self.delim = delim

    def feed(self, raw: bytes):
        self.buf += raw
        out = []
        while True:
            i = self.buf.find(self.delim)
            if i < 0:
                break
            out.append(bytes(self.buf[:i]))
            del self.buf[:i+len(self.delim)]
        return out
```

### 測試

```python
def test_line_framer_split():
    f = LineFramer(b"\n")
    assert f.feed(b"abc") == []
    assert f.feed(b"\n") == [b"abc"]
    assert f.feed(b"1\n2\n") == [b"1", b"2"]

def test_line_framer_two_packets_one_chunk():
    f = LineFramer(b"\n")
    assert f.feed(b"a\nb\n") == [b"a", b"b"]
```

### 工程意義
- 你不用開 UI 就能驗證「解析可靠性」
- 你在現場遇到怪資料也能重現與回歸測試

---

## 範例 6｜FSM 測試（用純 Python 狀態機也行）

```python
class ConnFSM:
    def __init__(self):
        self.state = "DISCONNECTED"

    def on_connect(self):
        if self.state == "DISCONNECTED":
            self.state = "CONNECTING"

    def on_connected(self):
        if self.state == "CONNECTING":
            self.state = "CONNECTED"

    def on_disconnect(self):
        self.state = "DISCONNECTED"

def test_fsm_flow():
    f = ConnFSM()
    f.on_connect()
    assert f.state == "CONNECTING"
    f.on_connected()
    assert f.state == "CONNECTED"
    f.on_disconnect()
    assert f.state == "DISCONNECTED"
```

> 你也可以用 QStateMachine，但純 Python FSM 更好測、更容易跑 CI。

---

# Part E｜CI（持續整合）：每次 commit 都自動跑測試與檢查

最常見：
- lint：ruff/flake8
- type check：mypy（可選）
- tests：pytest
- build：打包（可選）

你要的不是某個平台命令，而是「每次改動都不破」。

---

## 範例 7｜最小的 CI 思維（伪配置）

- push 到 repo
- 自動跑：`pytest -q`
- 過了才算「可交付」

你會發現：  
工控專案最怕的不是你寫慢，是你寫出「回歸 bug」現場炸。

---

# Part F｜Profiling：多媒體/工控最常死於效能與記憶體

## 1) CPU profiling（找出最慢的函數）
純 Python 可用：

- `cProfile`（標準庫）
- 或 line-level profiler（第三方）

概念：

```python
import cProfile, pstats

def main():
    # 跑一段你覺得慢的流程
    pass

pr = cProfile.Profile()
pr.enable()
main()
pr.disable()

pstats.Stats(pr).sort_stats("tottime").print_stats(30)
```

---

## 2) 記憶體洩漏：Qt 常見是「忘了 disconnect/忘了 deleteLater」

### 常見洩漏原因
- 不斷 new QThread/Worker 不釋放
- Signal connect 多次但不 disconnect（重複收到）
- 持有 QImage/QPixmap 大 buffer 的引用，永遠不放

### 工程做法（你應該養成）
- 每次建立 thread 都配套：
  - worker.finished → thread.quit
  - worker.deleteLater / thread.deleteLater
- 大 buffer 資料流做「latest-only」或 ring buffer（Lv8）

---

## 3) 觀測：每秒幀率、queue 長度、延遲（Metrics）

```python
import time
from collections import deque

class Metrics:
    def __init__(self):
        self.frames = 0
        self.t0 = time.time()
        self.lat_ms = deque(maxlen=100)

    def on_frame(self):
        self.frames += 1
        now = time.time()
        if now - self.t0 >= 1.0:
            fps = self.frames / (now - self.t0)
            self.frames = 0
            self.t0 = now
            return fps
        return None
```

把 fps/queue 長度顯示在 UI 上，你就能現場診斷：「是抓帧慢？解析慢？UI 刷新太快？」

---

# Part G｜可靠交付：部署/打包一致化 + Crash report

## 核心原則（你要記住）
- 設定、log、資料檔 **一定要寫到可寫路徑**
- 插件/模型/資源 **一定要跟著打包**
- 版本資訊 **一定要能顯示**（讓現場回報問題可定位）

---

## 範例 8｜版本資訊與 About（最常用）

```python
APP_VER = "1.3.7"
GIT_SHA = "abc1234"  # build 時注入

def about_text():
    return f"MyApp v{APP_VER} ({GIT_SHA})"
```

---

## 範例 9｜Crash report（最小）

```python
import sys, traceback, pathlib, datetime

def crash_hook(exctype, value, tb):
    msg = "".join(traceback.format_exception(exctype, value, tb))
    path = pathlib.Path("crash_reports")
    path.mkdir(exist_ok=True)
    fn = path / (datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt")
    fn.write_text(msg, encoding="utf-8")
    # 你也可以顯示對話框，提示使用者把檔案給你
    print("crashed, report:", fn)

sys.excepthook = crash_hook
```

---

# Part H｜安全與可靠：工控上位機常見基本功（你已經在意這塊）

如果你做 TLS/MQTT/工控協議，Lv9 會把它工程化：

- 驗證輸入（IP/Port/參數範圍）
- 通訊錯誤要有 FSM 與重連策略
- log 不要洩漏敏感資訊（token/密碼）
- 對外連線要有限制（白名單/ACL）
- 設備操作要有權限與確認（避免誤操作）

---

# Lv9 常見錯誤（很多人做到 Lv8 還是會炸）

- 所有東西硬寫死在 MainWindow
- Driver/Parser/Processor 不可替換 → 一改現場需求就重寫
- 沒有測試 → 修改一個小地方，整個系統回歸 bug
- 沒有 metrics → 現場卡頓你不知道原因
- 沒有 crash report → 閃退你無從重現

---

# Lv9 小作業（做完你就真的到產品級）

做一個「可插拔工控上位機骨架」：

1. EventBus：frame/state/log
2. Plugin loader：transport、parser、processor（至少 2 種 transport：TCP/Serial 的 stub 也行）
3. Parser 用純 Python，可單元測試（寫 5 個 pytest case）
4. FSM 管流程（Disconnected/Connecting/Connected/Error）
5. Model/View 顯示設備列表（更新單格）
6. Metrics 顯示 fps/queue 長度/延遲
7. Crash report + About 版本資訊

**要求**
- 換 plugin 只改 config，不改 UI code
- parser/fsm 都能在沒 GUI 的情況下跑測試

---

## Lv9 結尾：你真正學到的是什麼？

Lv9 讓你具備「把 Qt 專案做成平台」的能力：

- 變動點 plugin 化、配置化
- 核心平台穩定可維護
- 可測試、可觀測、可交付
- 多人協作不會互相踩爆

如果你要 Lv10，通常就是：
- **插件 ABI/版本管理、腳本化自動化、遠端更新**
- **資料回放（replay）+ 離線分析**
- **更嚴謹的架構（Hexagonal/Clean Architecture）**
- **安全強化（簽名、完整性檢查、沙盒）**

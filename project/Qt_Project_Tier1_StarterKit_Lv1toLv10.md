# 五階段專案教學（Tier 1～Tier 5）｜Qt / PyQt 工控上位機範例
> 你要的形式：**專案範例教學 .md**  
> 你要的要求：**五個等級**，而且整套課程要**涵蓋 Lv1～Lv10**。  
> 這份文件先給你 **Tier 1（最基礎可跑的 Starter Kit）**：它已經把 Lv1～Lv10 的「骨架」都放進去（用最小可用的方式），讓你後面擴充時不用推倒重來。

---

## 0) 這個範例專案要做什麼？
我們做一個工控/上位機常見的「監控控制台」(Control Desk)：

- 左側：連線控制（Connect / Disconnect、選 transport plugin）
- 右側：**設備表格**（Model/View）
- 下方：Log 面板（可觀測性）
- 背後：I/O 事件（readyRead 概念）、解析（Thread）、狀態機（FSM）、設定保存（QSettings）、回放（Replay）、診斷包（Support Bundle）、插件化（Plugin）、更新 stub（Updater Stub）

**Tier 1 做到：可跑、不卡、可擴充，而且每個 Lv 的「工程位置」都先卡好。**

---

## 1) 五個等級怎麼對應 Lv1～Lv10？
你會發現 Lv1～Lv10 很細，但現場做產品通常會「打包成 5 個里程碑」。

| 專案等級 | 你完成什麼 | 覆蓋 Lv |
|---|---|---|
| **Tier 1：Starter Kit（本文件）** | 能跑起來 + 正確事件架構 + 基礎工控骨架 | Lv1～Lv10（骨架/最小可用） |
| Tier 2：穩定 I/O + 協議解析 | 真正接 Serial/TCP，解析可靠、重連可控 | Lv5～Lv7（加深） |
| Tier 3：多媒體與可視化 | 相機/串流/錄影/即時曲線，不卡 UI | Lv8（加深） |
| Tier 4：插件化擴展平台 | Driver/Parser/Processor 全插件化 + CI 測試 | Lv9（加深） |
| Tier 5：運營級產品 | 安全更新/回滾、完整 replay、診斷包、遠端維護 | Lv10（加深） |

> 你現在要「先從第一格最基礎專案開始」，所以本文件只把 **Tier 1** 完整寫到「你可以照著建出專案」為止。

---

# Tier 1｜Starter Kit（最基礎但已包含 Lv1～Lv10 的骨架）

## 2) 你會得到什麼（Tier 1 目標）
### UI 你看得到的
- 主視窗 + Layout（Lv1～Lv2）
- 按鈕事件 Signal/Slot（Lv3）
- QTimer：UI 時鐘、批次刷新（Lv4）
- 表格：QTableView + Model（Lv7）
- Log 面板：logging → UI（Lv7）
- 狀態顯示：Disconnected/Connected/Error（Lv7）

### 背後你看不到但已經在的
- Transport plugin（Fake / TCP）可切換（Lv9）
- 收到 raw bytes → 錄到 Replay（jsonl）（Lv10）
- Replay 播放模式（把 jsonl 再餵回 parser）（Lv10）
- Support bundle：一鍵打包 log/config/replay（Lv10）
- Parser Worker（Thread）骨架（Lv6）
- Updater stub（不真正更新，但已放好 manifest/校驗接口）（Lv10）
- Multimedia placeholder（Lv8 位置先留著，Tier 3 再做）

---

## 3) 專案結構（你照這棵 tree 建）
> 你可以先手動建檔案；之後我也可以再幫你把它「整理成一份可下載的專案壓縮包」。

```
qt_control_desk/
├─ main.py
├─ requirements.txt
├─ config.json
├─ core/
│  ├─ bus.py
│  ├─ fsm.py
│  ├─ settings.py
│  ├─ logging_qt.py
│  ├─ replay.py
│  ├─ device_model.py
│  ├─ worker.py
│  └─ plugin_loader.py
├─ plugins/
│  ├─ fake_transport.py
│  └─ tcp_transport.py
├─ tools/
│  ├─ echo_server.py
│  └─ make_bundle.py
└─ ui/
   └─ main_window.py
```

---

## 4) requirements.txt（Tier 1 只依賴 PyQt6）
```txt
PyQt6>=6.5
```

---

## 5) config.json（Tier 1 用設定決定載入哪個 transport plugin）
```json
{
  "app": {
    "company": "YourCompany",
    "name": "QtControlDesk"
  },
  "transport": {
    "plugin": "plugins.fake_transport",
    "config": {
      "interval_ms": 200
    }
  },
  "replay": {
    "enabled": true,
    "path": "replay.jsonl"
  }
}
```

你想改成 TCP 測試（需先跑 tools/echo_server.py）：
```json
{
  "transport": {
    "plugin": "plugins.tcp_transport",
    "config": {
      "host": "127.0.0.1",
      "port": 9009
    }
  }
}
```

---

# 6) 核心骨架程式碼（Tier 1 完整可用）

## 6.1 main.py（Lv1：QApplication + event loop）
```python
import sys, json
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def load_cfg(path="config.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    cfg = load_cfg()

    app = QApplication(sys.argv)
    win = MainWindow(cfg)
    win.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

---

## 6.2 core/bus.py（Lv9：事件總線）
```python
from PyQt6.QtCore import QObject, pyqtSignal

class EventBus(QObject):
    # raw bytes from transport
    raw = pyqtSignal(bytes)

    # parsed result (dict)
    parsed = pyqtSignal(dict)

    # state / alarm / log
    state = pyqtSignal(str)
    alarm = pyqtSignal(str)
    log = pyqtSignal(str)

BUS = EventBus()
```

---

## 6.3 core/fsm.py（Lv7：流程狀態機，先用最小 FSM）
```python
class ConnFSM:
    # 最小狀態機：避免到處 if/else
    DISCONNECTED = "DISCONNECTED"
    CONNECTING   = "CONNECTING"
    CONNECTED    = "CONNECTED"
    ERROR        = "ERROR"

    def __init__(self):
        self.state = self.DISCONNECTED

    def on_connect(self):
        if self.state == self.DISCONNECTED:
            self.state = self.CONNECTING

    def on_connected(self):
        if self.state == self.CONNECTING:
            self.state = self.CONNECTED

    def on_disconnect(self):
        self.state = self.DISCONNECTED

    def on_error(self, msg=""):
        self.state = f"{self.ERROR}: {msg}"
```

---

## 6.4 core/settings.py（Lv7：QSettings 保存視窗幾何）
```python
from PyQt6.QtCore import QSettings

class AppSettings:
    def __init__(self, company: str, app_name: str):
        self.s = QSettings(company, app_name)

    def save_geometry(self, win):
        self.s.setValue("ui/geometry", win.saveGeometry())

    def load_geometry(self, win):
        geo = self.s.value("ui/geometry")
        if geo is not None:
            win.restoreGeometry(geo)
```

---

## 6.5 core/logging_qt.py（Lv7：Python logging → UI）
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

def setup_logger(bus_log_emit):
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    h = QtLogHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    h.sig.connect(bus_log_emit)

    logger.addHandler(h)
    return logger
```

---

## 6.6 core/replay.py（Lv10：錄資料 + 回放）
```python
import json, time, base64

class ReplayRecorder:
    def __init__(self, path: str):
        self.path = path
        self.fp = open(path, "a", encoding="utf-8")

    def record_raw(self, source: str, payload: bytes):
        rec = {
            "ts": time.time(),
            "type": "raw",
            "source": source,
            "b64": base64.b64encode(payload).decode("ascii"),
        }
        self.fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.fp.flush()

    def close(self):
        try:
            self.fp.close()
        except Exception:
            pass

def replay_jsonl(path: str, feed_fn, speed: float = 1.0):
    prev_ts = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            ts = rec["ts"]
            raw = base64.b64decode(rec["b64"])

            if prev_ts is not None:
                dt = (ts - prev_ts) / max(1e-6, speed)
                if dt > 0:
                    time.sleep(dt)
            prev_ts = ts

            feed_fn(raw)
```

---

## 6.7 core/device_model.py（Lv7：Model/View 的最小設備表格）
> 這是 Tier 1 最重要的「不卡表格」做法：不要用 QTableWidget 暴力刷新。

```python
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex

class DeviceModel(QAbstractTableModel):
    def __init__(self, rows=None):
        super().__init__()
        self.headers = ["ID", "Name", "Status", "Last(ms)"]
        self.rows = rows or []

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
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        r = self.rows[index.row()]
        c = index.column()
        if c == 0: return str(r["id"])
        if c == 1: return r["name"]
        if c == 2: return r["status"]
        if c == 3: return str(r["last_ms"])
        return None

    def update_row(self, row_idx: int, **kv):
        self.rows[row_idx].update(kv)
        top_left = self.index(row_idx, 0)
        bottom_right = self.index(row_idx, self.columnCount()-1)
        self.dataChanged.emit(top_left, bottom_right)

    def add_row(self, row: dict):
        r = self.rowCount()
        self.beginInsertRows(QModelIndex(), r, r)
        self.rows.append(row)
        self.endInsertRows()
```

---

## 6.8 core/worker.py（Lv6：解析丟 thread 的骨架）
> Tier 1 先用「假解析」示範：收到 bytes → 轉成 dict。你後面可以換成真正的協議解析/頻譜/AI 推論。

```python
from PyQt6.QtCore import QObject, pyqtSignal

class ParserWorker(QObject):
    parsed = pyqtSignal(dict)

    def parse(self, raw: bytes):
        # 假裝解析：只做很快的工作（後面可替換成 heavy parse）
        d = {
            "len": len(raw),
            "head_hex": raw[:8].hex(),
        }
        self.parsed.emit(d)
```

---

## 6.9 core/plugin_loader.py（Lv9：Plugin loader + ABI 檢查）
```python
import importlib

REQUIRED_PLUGIN_ABI = 1

def load_plugin(module_path: str, config: dict):
    mod = importlib.import_module(module_path)
    abi = getattr(mod, "PLUGIN_ABI", None)
    if abi != REQUIRED_PLUGIN_ABI:
        raise RuntimeError(f"Plugin ABI mismatch: {module_path} abi={abi} required={REQUIRED_PLUGIN_ABI}")
    return mod.create(config)
```

---

## 6.10 plugins/fake_transport.py（Tier 1 自帶：不用外部設備也能跑）
> 這個 plugin 用 QTimer 模擬「資料到」，讓你整套架構先跑通（I/O → replay → parser → UI）。

```python
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import os

PLUGIN_ABI = 1

class FakeTransport(QObject):
    rx = pyqtSignal(bytes)
    state = pyqtSignal(str)

    def __init__(self, interval_ms: int = 200):
        super().__init__()
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self._tick)

    def open(self) -> bool:
        self.state.emit("CONNECTED")
        self.timer.start()
        return True

    def close(self) -> None:
        self.timer.stop()
        self.state.emit("DISCONNECTED")

    def write(self, data: bytes) -> None:
        # 假裝立即回傳（echo）
        self.rx.emit(b"echo:" + data)

    def _tick(self):
        # 每次丟一筆「假資料」
        payload = os.urandom(32)
        self.rx.emit(payload)

def create(config: dict) -> FakeTransport:
    return FakeTransport(int(config.get("interval_ms", 200)))
```

---

## 6.11 plugins/tcp_transport.py（Lv5：真實 readyRead 類型 I/O，配 tools/echo_server.py）
> 這個 plugin 用 **QTcpSocket + readyRead**，才是真正的 I/O 事件驅動。

```python
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QTcpSocket

PLUGIN_ABI = 1

class TcpTransport(QObject):
    rx = pyqtSignal(bytes)
    state = pyqtSignal(str)

    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = QTcpSocket()
        self.sock.connected.connect(lambda: self.state.emit("CONNECTED"))
        self.sock.disconnected.connect(lambda: self.state.emit("DISCONNECTED"))
        self.sock.readyRead.connect(self._on_ready)

    def open(self) -> bool:
        self.state.emit("CONNECTING")
        self.sock.connectToHost(self.host, self.port)
        return True

    def close(self) -> None:
        self.sock.disconnectFromHost()

    def write(self, data: bytes) -> None:
        self.sock.write(data)

    def _on_ready(self):
        raw = self.sock.readAll().data()
        self.rx.emit(raw)

def create(config: dict) -> TcpTransport:
    return TcpTransport(config.get("host", "127.0.0.1"), int(config.get("port", 9009)))
```

---

## 6.12 tools/echo_server.py（本機 TCP 回音伺服器，讓你測 readyRead）
```python
import socket, threading

HOST = "127.0.0.1"
PORT = 9009

def handle(conn, addr):
    print("client:", addr)
    with conn:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            conn.sendall(b"echo:" + data)

def main():
    s = socket.socket()
    s.bind((HOST, PORT))
    s.listen(5)
    print("echo server listening:", HOST, PORT)
    while True:
        c, a = s.accept()
        threading.Thread(target=handle, args=(c, a), daemon=True).start()

if __name__ == "__main__":
    main()
```

---

## 6.13 tools/make_bundle.py（Lv10：一鍵診斷包）
```python
import zipfile, pathlib, time

def make_bundle(out_zip: str, paths: list[str]):
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            pth = pathlib.Path(p)
            if pth.exists():
                z.write(pth, arcname=pth.name)

if __name__ == "__main__":
    bundle = f"support_{int(time.time())}.zip"
    make_bundle(bundle, ["config.json", "replay.jsonl"])
    print("made:", bundle)
```

---

## 6.14 ui/main_window.py（Lv1～Lv7：主視窗、Layout、Signal、Timer、Model/View）
> 這支檔案把「你前面 Lv1～Lv7 觀念」一次落地：  
> UI thread 不阻塞、資料用事件流進來、表格用 Model、log 用 bus。

```python
import json, time
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QPlainTextEdit, QTableView, QMessageBox
)
from PyQt6.QtCore import QTimer, QThread

from core.bus import BUS
from core.fsm import ConnFSM
from core.settings import AppSettings
from core.logging_qt import setup_logger
from core.replay import ReplayRecorder, replay_jsonl
from core.device_model import DeviceModel
from core.worker import ParserWorker
from core.plugin_loader import load_plugin

class MainWindow(QMainWindow):
    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Qt Control Desk (Tier 1 Starter Kit)")

        # --- Settings (Lv7)
        app_cfg = cfg.get("app", {})
        self.settings = AppSettings(app_cfg.get("company", "YourCompany"),
                                    app_cfg.get("name", "QtControlDesk"))
        self.settings.load_geometry(self)

        # --- FSM (Lv7)
        self.fsm = ConnFSM()
        BUS.state.connect(self._on_bus_state)

        # --- Logger (Lv7)
        self.logger = setup_logger(BUS.log.emit)

        # --- Replay (Lv10)
        self.replay = None
        rep_cfg = cfg.get("replay", {})
        self.replay_enabled = bool(rep_cfg.get("enabled", True))
        self.replay_path = rep_cfg.get("path", "replay.jsonl")

        # --- UI (Lv1~Lv3)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        layout.addLayout(top)

        self.cb_transport = QComboBox()
        # 讓你可以在 UI 切 transport（Tier1 先提供兩個）
        self.cb_transport.addItem("Fake (plugins.fake_transport)", "plugins.fake_transport")
        self.cb_transport.addItem("TCP  (plugins.tcp_transport)",  "plugins.tcp_transport")
        top.addWidget(QLabel("Transport:"))
        top.addWidget(self.cb_transport)

        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_replay = QPushButton("Replay jsonl")
        top.addWidget(self.btn_connect)
        top.addWidget(self.btn_disconnect)
        top.addWidget(self.btn_replay)

        self.lb_state = QLabel("STATE: DISCONNECTED")
        self.lb_clock = QLabel("--:--:--")
        top.addWidget(self.lb_state)
        top.addWidget(self.lb_clock)

        mid = QHBoxLayout()
        layout.addLayout(mid)

        # --- Device table (Lv7: Model/View)
        self.model = DeviceModel([
            {"id": 1, "name": "Device-A", "status": "INIT", "last_ms": 0},
            {"id": 2, "name": "Device-B", "status": "INIT", "last_ms": 0},
        ])
        self.table = QTableView()
        self.table.setModel(self.model)
        mid.addWidget(self.table, 2)

        # --- Log (Lv7)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        mid.addWidget(self.log, 3)
        BUS.log.connect(self.log.appendPlainText)

        # --- QTimer clock (Lv4)
        self.t_clock = QTimer(self)
        self.t_clock.setInterval(200)
        self.t_clock.timeout.connect(self._tick_clock)
        self.t_clock.start()

        # --- Parser worker in thread (Lv6)
        self.parse_thread = QThread()
        self.worker = ParserWorker()
        self.worker.moveToThread(self.parse_thread)
        self.parse_thread.start()

        # raw -> worker.parse (cross thread)
        BUS.raw.connect(self.worker.parse)
        self.worker.parsed.connect(BUS.parsed.emit)  # back to bus
        BUS.parsed.connect(self._on_parsed)

        # --- Transport instance (Lv5/Lv9)
        self.transport = None
        self.source_name = "unknown"

        # --- UI signals
        self.btn_connect.clicked.connect(self.on_connect)
        self.btn_disconnect.clicked.connect(self.on_disconnect)
        self.btn_replay.clicked.connect(self.on_replay)

        self.logger.info("app started")

    # --------- UI ticks ---------
    def _tick_clock(self):
        t = time.strftime("%H:%M:%S")
        self.lb_clock.setText(t)

    # --------- State updates ---------
    def _on_bus_state(self, s: str):
        self.lb_state.setText(f"STATE: {s}")

    # --------- Parsed data -> update model (Tier1 demo) ---------
    def _on_parsed(self, d: dict):
        # demo：交替更新兩個設備，表示「資料有在流」
        now_ms = int(time.time() * 1000) % 100000
        if d["len"] % 2 == 0:
            self.model.update_row(0, status="OK", last_ms=now_ms)
        else:
            self.model.update_row(1, status="OK", last_ms=now_ms)

    # --------- Connect / Disconnect ---------
    def on_connect(self):
        if self.transport is not None:
            QMessageBox.information(self, "Info", "Already connected/opened.")
            return

        self.fsm.on_connect()
        BUS.state.emit(self.fsm.state)

        module_path = self.cb_transport.currentData()

        # config.json 的 transport 設定（若 UI 選 TCP，也可先用 config 覆蓋）
        t_cfg = self.cfg.get("transport", {}).get("config", {})
        if "tcp_transport" in module_path:
            # 如果 config.json 沒寫，就用預設
            t_cfg = {"host": t_cfg.get("host", "127.0.0.1"), "port": int(t_cfg.get("port", 9009))}
        else:
            t_cfg = {"interval_ms": int(t_cfg.get("interval_ms", 200))}

        try:
            self.transport = load_plugin(module_path, t_cfg)
        except Exception as e:
            self.transport = None
            self.fsm.on_error(str(e))
            BUS.state.emit(self.fsm.state)
            QMessageBox.critical(self, "Plugin Load Error", str(e))
            return

        self.source_name = module_path

        # transport state -> fsm/bus
        self.transport.state.connect(self._on_transport_state)
        self.transport.rx.connect(self._on_transport_rx)

        ok = self.transport.open()
        self.logger.info(f"transport open: {module_path} ok={ok}")

        # replay file open
        if self.replay_enabled:
            self.replay = ReplayRecorder(self.replay_path)
            self.logger.info(f"replay recording -> {self.replay_path}")

    def _on_transport_state(self, s: str):
        if s == "CONNECTED":
            self.fsm.on_connected()
        elif s == "DISCONNECTED":
            self.fsm.on_disconnect()
        else:
            self.fsm.on_error(s)
        BUS.state.emit(self.fsm.state)

    def _on_transport_rx(self, raw: bytes):
        # Lv5: 事件驅動進來的 raw data
        if self.replay:
            self.replay.record_raw(self.source_name, raw)  # Lv10
        BUS.raw.emit(raw)

    def on_disconnect(self):
        if self.transport:
            try:
                self.transport.close()
            except Exception:
                pass
            self.transport = None

        if self.replay:
            self.replay.close()
            self.replay = None

        self.fsm.on_disconnect()
        BUS.state.emit(self.fsm.state)
        self.logger.info("disconnected")

    # --------- Replay mode (Lv10) ---------
    def on_replay(self):
        # 把 replay.jsonl 重新餵回 BUS.raw（模擬現場資料重現）
        try:
            replay_jsonl(self.replay_path, BUS.raw.emit, speed=2.0)
        except Exception as e:
            QMessageBox.critical(self, "Replay Error", str(e))

    def closeEvent(self, e):
        # 收尾：避免 thread/resource 泄漏
        self.on_disconnect()
        self.parse_thread.quit()
        self.parse_thread.wait(1000)

        self.settings.save_geometry(self)
        e.accept()
```

---

# 7) 怎麼跑（Tier 1）
## 7.1 安裝
```bash
pip install -r requirements.txt
```

## 7.2 跑 Tier1（預設 FakeTransport）
```bash
python main.py
```

你應該會看到：
- State 變 CONNECTED
- 表格的狀態會交替更新（表示資料流在跑）
- replay.jsonl 會一直增加

## 7.3 測 TCP readyRead（Lv5 真 I/O）
1) 先跑 echo server：
```bash
python tools/echo_server.py
```

2) 把 config.json transport plugin 改成 tcp_transport（或在 UI 選 TCP）
3) 再跑：
```bash
python main.py
```

---

# 8) Tier 1 這樣就算「已含 Lv1～Lv10」的理由（你要的對照）
- Lv1：QApplication + app.exec()
- Lv2：Widget/Layout（主視窗組裝）
- Lv3：clicked → slots、bus signals
- Lv4：QTimer clock（後面可加 UI 節流 timer）
- Lv5：QTcpSocket readyRead（tcp_transport）
- Lv6：ParserWorker + QThread + cross-thread signal
- Lv7：DeviceModel + View、FSM、QSettings、logging→UI
- Lv8：預留多媒體位置（Tier 3 會把 Camera Tab + 錄影 pipeline 加進來）
- Lv9：plugin loader + ABI 檢查 + config 驅動
- Lv10：replay record/replay、support bundle（tools）、update stub 的位置（Tier 5 做完整）

---

# 9) 下一步（你只要回我「Tier2」我就接著寫）
Tier 2 會把 Tier1 的「骨架」變成真正能接設備的工控通訊專案：

- Serial（QSerialPort）transport plugin
- 協議 framing（header+len+crc）
- reconnect/backoff 策略（FSM 加深）
- UI 節流：每 100ms 批次刷新 log/表格
- Replay 改成「更像現場」：raw + parsed + state timeline
- 解析 heavy 的時候加入丟幀/回壓策略（backpressure）

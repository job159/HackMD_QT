# Tier 2｜穩定 I/O + 協議解析（Serial/TCP）專案教學.md
> 接續 Tier 1：你已經有「不卡 UI 的骨架」  
> Tier 2 目標：把它變成 **真的能接設備、能抗雜訊、能重連、能回放重現** 的工控通訊框架  
> 覆蓋重點：**Lv5～Lv7 加深 + Lv9～Lv10 實用化**（但仍然延續 Lv1～Lv4/Lv6 的正確架構）

---

## 0) Tier 2 你會做到什麼（工程驗收清單）
### ✅ 連線與 I/O 穩定
- 支援 **Serial（QSerialPort）** 與 **TCP（QTcpSocket）**（插件化）
- readyRead 事件驅動收資料，不用 while
- 斷線偵測 + **自動重連**（指數退避 backoff）
- 連線流程用 FSM（Disconnected / Connecting / Handshaking / Online / Error）

### ✅ 協議解析可靠
- 支援 framing：`[HEADER][LEN][PAYLOAD][CRC16]`（最常見工控封包）
- 处理 **半包、黏包、雜訊**（buffer + resync）
- CRC 檢查、錯誤計數、丟包策略（回壓/backpressure）

### ✅ UI 不被刷爆
- Log/表格/狀態改成 **批次刷新**（QTimer 100ms）
- 解析重工作放 background thread（Lv6 延伸）
- 「只保留最新」策略避免 queue 堆積

### ✅ Replay 更像現場
- replay.jsonl 不只記 raw：也記 state/parsed timeline
- 回放時能重跑：transport → framer → parser → fsm → ui

### ✅ 測試（最小）
- framer 的半包/黏包/雜訊測試（pytest）
- CRC 測試

---

# 1) 專案結構（Tier 2 擴充版）
> 基於 Tier 1 的 tree，新增/替換以下檔案（✅新增 / 🔁更新）

```
qt_control_desk/
├─ main.py                         🔁（小改：讀 cfg + 啟動）
├─ requirements.txt                🔁（可選：加 pytest）
├─ config.json                     🔁（serial/tcp 的 config）
├─ core/
│  ├─ bus.py                       🔁（多加 metrics/replay 事件）
│  ├─ fsm.py                       🔁（加 Handshaking/Online/Error）
│  ├─ settings.py                  （同 Tier1）
│  ├─ logging_qt.py                （同 Tier1）
│  ├─ replay.py                    🔁（記 raw + state + parsed）
│  ├─ device_model.py              （同 Tier1）
│  ├─ plugin_loader.py             （同 Tier1）
│  ├─ framer.py                    ✅（封包切分/重組/重同步）
│  ├─ crc16.py                     ✅（CRC16-IBM/MODBUS）
│  ├─ backoff.py                   ✅（指數退避）
│  ├─ metrics.py                   ✅（fps/queue/錯誤計數）
│  ├─ pipeline.py                  ✅（transport→framer→parser→bus）
│  └─ workers/
│     ├─ parser_worker.py          🔁（解析可變重工作）
│     └─ processor_worker.py       ✅（可選：後處理/AI/頻譜）
├─ plugins/
│  ├─ fake_transport.py            （仍可保留）
│  ├─ tcp_transport.py             🔁（加 error/timeout 事件）
│  └─ serial_transport.py          ✅（QSerialPort readyRead）
├─ tests/                          ✅（可選）
│  ├─ test_framer.py
│  └─ test_crc16.py
└─ ui/
   └─ main_window.py               🔁（加入：重連控制、節流、metrics顯示）
```

---

# 2) requirements.txt（建議）
```txt
PyQt6>=6.5
pytest>=7.0
```
> pytest 只是跑 tests 用，不加也可。

---

# 3) config.json（Tier2：選 Serial 或 TCP）
### 3.1 Serial（最常見工控）
```json
{
  "app": { "company": "YourCompany", "name": "QtControlDesk" },
  "transport": {
    "plugin": "plugins.serial_transport",
    "config": { "port": "COM3", "baud": 115200, "data_bits": 8, "parity": "N", "stop_bits": 1 }
  },
  "protocol": {
    "header_hex": "AA55",
    "crc": "modbus"
  },
  "replay": { "enabled": true, "path": "replay.jsonl" }
}
```

### 3.2 TCP（測試或設備網路化）
```json
{
  "transport": {
    "plugin": "plugins.tcp_transport",
    "config": { "host": "127.0.0.1", "port": 9009 }
  },
  "protocol": { "header_hex": "AA55", "crc": "modbus" }
}
```

---

# 4) Tier2 核心新增檔案（完整可貼）

## 4.1 core/crc16.py（CRC16-MODBUS / IBM 常用）
```python
def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

def crc16_bytes_le(crc: int) -> bytes:
    # little-endian: low byte first (Modbus)
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])
```

---

## 4.2 core/framer.py（重點：半包/黏包/雜訊 resync）
### 協議格式（你後面可改）
```
[0..1]   HEADER 2 bytes  (AA 55)
[2]      LEN    1 byte   (payload length)
[3..]    PAYLOAD LEN bytes
[last2]  CRC16  2 bytes  (CRC over HEADER+LEN+PAYLOAD)
```

```python
from dataclasses import dataclass
from typing import List, Optional
from core.crc16 import crc16_modbus

@dataclass
class Frame:
    payload: bytes
    ok: bool
    err: Optional[str] = None

class Framer:
    def __init__(self, header: bytes):
        if len(header) < 2:
            raise ValueError("header must be >=2 bytes")
        self.header = header
        self.buf = bytearray()
        self.bad_crc = 0
        self.bad_header = 0

    def feed(self, raw: bytes) -> List[Frame]:
        self.buf += raw
        out: List[Frame] = []

        while True:
            # 1) 找 header（resync：丟掉 header 前雜訊）
            idx = self.buf.find(self.header)
            if idx < 0:
                # header 不存在：保留最後 1 byte（避免切掉可能的 header 前綴）
                if len(self.buf) > len(self.header) - 1:
                    self.buf = self.buf[-(len(self.header)-1):]
                break

            if idx > 0:
                # 丟掉雜訊
                del self.buf[:idx]
                self.bad_header += 1

            # 現在 buf[0:len(header)] == header
            if len(self.buf) < len(self.header) + 1:
                break  # 等 LEN

            payload_len = self.buf[len(self.header)]
            total = len(self.header) + 1 + payload_len + 2  # +CRC16

            if len(self.buf) < total:
                break  # 等完整封包

            packet = bytes(self.buf[:total])
            del self.buf[:total]

            body = packet[:-2]
            crc_recv = packet[-2] | (packet[-1] << 8)
            crc_calc = crc16_modbus(body)

            if crc_recv != crc_calc:
                self.bad_crc += 1
                out.append(Frame(payload=b"", ok=False, err="CRC"))
                continue

            payload = packet[len(self.header)+1:-2]
            out.append(Frame(payload=payload, ok=True))

        return out
```

---

## 4.3 core/backoff.py（指數退避：重連很重要）
```python
import random

class Backoff:
    def __init__(self, base=0.5, factor=2.0, max_s=10.0, jitter=0.2):
        self.base = base
        self.factor = factor
        self.max_s = max_s
        self.jitter = jitter
        self.n = 0

    def reset(self):
        self.n = 0

    def next_delay(self) -> float:
        d = min(self.max_s, self.base * (self.factor ** self.n))
        self.n += 1
        # jitter：避免多台設備同時重連造成突波
        j = d * self.jitter * (random.random() * 2 - 1)
        return max(0.0, d + j)
```

---

## 4.4 core/metrics.py（可觀測：fps/queue/錯誤）
```python
import time
from collections import deque

class Metrics:
    def __init__(self):
        self.frames_in = 0
        self.frames_ok = 0
        self.frames_bad = 0
        self.t0 = time.time()
        self.fps = 0.0
        self.lat_ms = deque(maxlen=100)

    def on_frame_in(self):
        self.frames_in += 1

    def on_frame_ok(self):
        self.frames_ok += 1

    def on_frame_bad(self):
        self.frames_bad += 1

    def tick_1s(self):
        now = time.time()
        dt = now - self.t0
        if dt >= 1.0:
            self.fps = self.frames_in / dt
            self.frames_in = 0
            self.t0 = now
            return self.fps
        return None
```

---

## 4.5 core/bus.py（Tier2：多加 metrics/replay events）
```python
from PyQt6.QtCore import QObject, pyqtSignal

class EventBus(QObject):
    raw = pyqtSignal(bytes)        # transport raw
    frame = pyqtSignal(object)     # Frame from framer
    parsed = pyqtSignal(dict)      # parsed dict

    state = pyqtSignal(str)        # FSM state text
    log = pyqtSignal(str)

    metrics = pyqtSignal(dict)     # fps/errors
    replay = pyqtSignal(dict)      # record item (raw/state/parsed)

BUS = EventBus()
```

---

## 4.6 core/fsm.py（Tier2：加 Handshaking/Online/Error）
```python
class ConnFSM:
    DISCONNECTED = "DISCONNECTED"
    CONNECTING   = "CONNECTING"
    HANDSHAKE    = "HANDSHAKE"
    ONLINE       = "ONLINE"
    ERROR        = "ERROR"

    def __init__(self):
        self.state = self.DISCONNECTED

    def on_connect(self):
        if self.state == self.DISCONNECTED:
            self.state = self.CONNECTING

    def on_connected(self):
        if self.state == self.CONNECTING:
            self.state = self.HANDSHAKE

    def on_handshake_ok(self):
        if self.state == self.HANDSHAKE:
            self.state = self.ONLINE

    def on_disconnect(self):
        self.state = self.DISCONNECTED

    def on_error(self, msg=""):
        self.state = f"{self.ERROR}: {msg}"
```

---

## 4.7 plugins/serial_transport.py（Tier2 重點：QSerialPort readyRead）
```python
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtSerialPort import QSerialPort

PLUGIN_ABI = 1

class SerialTransport(QObject):
    rx = pyqtSignal(bytes)
    state = pyqtSignal(str)

    def __init__(self, port: str, baud: int, data_bits=8, parity="N", stop_bits=1):
        super().__init__()
        self.ser = QSerialPort()
        self.ser.setPortName(port)
        self.ser.setBaudRate(int(baud))
        self.ser.readyRead.connect(self._on_ready)
        self.ser.errorOccurred.connect(self._on_error)

        # data bits
        if int(data_bits) == 7:
            self.ser.setDataBits(QSerialPort.DataBits.Data7)
        else:
            self.ser.setDataBits(QSerialPort.DataBits.Data8)

        # parity
        p = str(parity).upper()
        if p == "E":
            self.ser.setParity(QSerialPort.Parity.EvenParity)
        elif p == "O":
            self.ser.setParity(QSerialPort.Parity.OddParity)
        else:
            self.ser.setParity(QSerialPort.Parity.NoParity)

        # stop bits
        if int(stop_bits) == 2:
            self.ser.setStopBits(QSerialPort.StopBits.TwoStop)
        else:
            self.ser.setStopBits(QSerialPort.StopBits.OneStop)

    def open(self) -> bool:
        self.state.emit("CONNECTING")
        ok = self.ser.open(QSerialPort.OpenModeFlag.ReadWrite)
        if ok:
            self.state.emit("CONNECTED")
        else:
            self.state.emit("ERROR: open failed")
        return ok

    def close(self) -> None:
        self.ser.close()
        self.state.emit("DISCONNECTED")

    def write(self, data: bytes) -> None:
        self.ser.write(data)

    def _on_ready(self):
        raw = self.ser.readAll().data()
        self.rx.emit(raw)

    def _on_error(self, err):
        # 重要：serial 斷線、I/O error 要往上報，讓 FSM/重連處理
        if err == QSerialPort.SerialPortError.NoError:
            return
        self.state.emit(f"ERROR: {err}")

def create(config: dict) -> SerialTransport:
    return SerialTransport(
        config.get("port", "COM3"),
        int(config.get("baud", 115200)),
        int(config.get("data_bits", 8)),
        config.get("parity", "N"),
        int(config.get("stop_bits", 1)),
    )
```

---

## 4.8 plugins/tcp_transport.py（Tier2：補 error 事件）
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
        self.sock.errorOccurred.connect(self._on_error)

    def open(self) -> bool:
        self.state.emit("CONNECTING")
        self.sock.connectToHost(self.host, self.port)
        return True

    def close(self) -> None:
        self.sock.disconnectFromHost()

    def write(self, data: bytes) -> None:
        self.sock.write(data)

    def _on_ready(self):
        self.rx.emit(self.sock.readAll().data())

    def _on_error(self, err):
        self.state.emit(f"ERROR: {err}")

def create(config: dict) -> TcpTransport:
    return TcpTransport(config.get("host", "127.0.0.1"), int(config.get("port", 9009)))
```

---

## 4.9 core/workers/parser_worker.py（Tier2：解析 heavy 化的準備）
> 你可以在這裡做：CRC OK 後 payload 轉 dict、解壓縮、頻譜、AI 推論…  
> Tier2 先示範「解析 + 小延遲」，並提供「丟幀策略」的 hook。

```python
from PyQt6.QtCore import QObject, pyqtSignal

class ParserWorker(QObject):
    parsed = pyqtSignal(dict)

    def parse_payload(self, payload: bytes):
        # Tier2 demo：假設 payload[0] 是 device_id，payload[1] 是 status code
        if len(payload) >= 2:
            dev_id = payload[0]
            status_code = payload[1]
        else:
            dev_id = 0
            status_code = 255

        d = {
            "dev_id": int(dev_id),
            "status_code": int(status_code),
            "payload_len": len(payload),
            "payload_head": payload[:8].hex(),
        }
        self.parsed.emit(d)
```

---

## 4.10 core/pipeline.py（Tier2 核心：transport→framer→parser→bus + metrics + backpressure）
> 這是 Tier2 的「工程心臟」：把資料流集中管理，UI 只接 bus。

```python
import time
from PyQt6.QtCore import QObject, QThread, QTimer

from core.bus import BUS
from core.framer import Framer
from core.metrics import Metrics
from core.workers.parser_worker import ParserWorker

class Pipeline(QObject):
    def __init__(self, header: bytes):
        super().__init__()
        self.framer = Framer(header)
        self.metrics = Metrics()

        # Parser worker thread
        self.parse_thread = QThread()
        self.parser = ParserWorker()
        self.parser.moveToThread(self.parse_thread)
        self.parse_thread.start()

        # raw -> feed framer（在 UI thread 做也行，因為只是 buffer/切包）
        BUS.raw.connect(self.on_raw)

        # frame ok -> parser.parse_payload（跨 thread）
        BUS.frame.connect(self.on_frame)

        # parser result back to bus
        self.parser.parsed.connect(BUS.parsed.emit)

        # metrics timer（每秒發一次）
        self.t = QTimer()
        self.t.setInterval(1000)
        self.t.timeout.connect(self.publish_metrics)
        self.t.start()

        # backpressure：只保留最新 payload（避免 queue 堆爆）
        self._latest_payload = None
        self._busy = False

    def on_raw(self, raw: bytes):
        self.metrics.on_frame_in()
        frames = self.framer.feed(raw)
        for fr in frames:
            if not fr.ok:
                self.metrics.on_frame_bad()
                continue
            self.metrics.on_frame_ok()
            BUS.frame.emit(fr)

    def on_frame(self, fr):
        # latest-only 策略：如果 parser 很慢，永遠只保留最新 payload
        self._latest_payload = fr.payload
        if self._busy:
            return
        self._busy = True
        self._drain_latest()

    def _drain_latest(self):
        # 把最新 payload 丟給 parser
        payload = self._latest_payload
        self._latest_payload = None

        # 這裡用 Qt 的 queued connection：呼叫 parser slot
        self.parser.parse_payload(payload)

        # parse_payload 很快會回來；如果你做 heavy parse，
        # 建議改成：parser.finished signal → _on_parser_done 再 drain。
        self._busy = False
        if self._latest_payload is not None:
            self._drain_latest()

    def publish_metrics(self):
        BUS.metrics.emit({
            "fps": round(self.metrics.fps, 2),
            "bad_crc": self.framer.bad_crc,
            "bad_header": self.framer.bad_header
        })

    def shutdown(self):
        self.parse_thread.quit()
        self.parse_thread.wait(1000)
```

> **重要提醒（工程真相）**：如果你的 parse 真的是 heavy，`_busy` 的處理要改成「parser 完成才 release busy」。  
> Tier2 先把骨架放好，Tier3/4 再把 heavy parse 流程做更嚴謹。

---

## 4.11 core/replay.py（Tier2：記 raw + state + parsed）
```python
import json, time, base64

class ReplayRecorder:
    def __init__(self, path: str):
        self.path = path
        self.fp = open(path, "a", encoding="utf-8")

    def record(self, item: dict):
        item["ts"] = time.time()
        self.fp.write(json.dumps(item, ensure_ascii=False) + "\n")
        self.fp.flush()

    def record_raw(self, source: str, payload: bytes):
        self.record({
            "type": "raw",
            "source": source,
            "b64": base64.b64encode(payload).decode("ascii")
        })

    def record_state(self, state: str):
        self.record({ "type": "state", "state": state })

    def record_parsed(self, d: dict):
        self.record({ "type": "parsed", "data": d })

    def close(self):
        try: self.fp.close()
        except: pass

def replay_jsonl(path: str, on_raw, on_state=None, on_parsed=None, speed: float=1.0):
    prev_ts = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            ts = rec["ts"]
            if prev_ts is not None:
                dt = (ts - prev_ts) / max(1e-6, speed)
                if dt > 0: time.sleep(dt)
            prev_ts = ts

            t = rec.get("type")
            if t == "raw":
                raw = base64.b64decode(rec["b64"])
                on_raw(raw)
            elif t == "state" and on_state:
                on_state(rec["state"])
            elif t == "parsed" and on_parsed:
                on_parsed(rec["data"])
```

---

# 5) UI：main_window.py（Tier2 重點改法：節流 + 重連 + metrics）
你不需要整份重貼（太長），這裡是「Tier2 必改的重點片段」。

## 5.1 加入：metrics 顯示 + 批次刷新（100ms）
```python
from collections import deque
from PyQt6.QtCore import QTimer
from core.bus import BUS

self.pending_logs = deque()
BUS.log.connect(lambda s: self.pending_logs.append(s))

self.pending_parsed = deque(maxlen=200)  # parsed 資料也節流
BUS.parsed.connect(lambda d: self.pending_parsed.append(d))

self.ui_flush = QTimer(self)
self.ui_flush.setInterval(100)
self.ui_flush.timeout.connect(self.flush_ui)
self.ui_flush.start()

def flush_ui(self):
    # 每次最多刷 50 行 log
    for _ in range(min(50, len(self.pending_logs))):
        self.log.appendPlainText(self.pending_logs.popleft())

    # 每次最多吃 10 筆 parsed（更新 model）
    for _ in range(min(10, len(self.pending_parsed))):
        d = self.pending_parsed.popleft()
        self.apply_parsed(d)
```

## 5.2 apply_parsed：只更新必要的 row（Model/View）
```python
def apply_parsed(self, d):
    dev_id = d.get("dev_id", 0)
    idx = 0 if dev_id % 2 == 0 else 1
    self.model.update_row(idx, status=f"S{d.get('status_code')}", last_ms=int(time.time()*1000)%100000)
```

## 5.3 重連：backoff + QTimer
```python
from core.backoff import Backoff
self.backoff = Backoff()
self.reconnect_timer = QTimer(self)
self.reconnect_timer.setSingleShot(True)
self.reconnect_timer.timeout.connect(self.on_connect)

def on_transport_state(self, s):
    # s 可能是 CONNECTED / DISCONNECTED / ERROR:...
    BUS.state.emit(s)
    if s.startswith("ERROR") or s == "DISCONNECTED":
        # 觸發重連
        delay = int(self.backoff.next_delay() * 1000)
        self.reconnect_timer.start(delay)
    elif s == "CONNECTED":
        self.backoff.reset()
```

---

# 6) 測試（tests）：你至少要把 framer 測起來
## 6.1 tests/test_crc16.py
```python
from core.crc16 import crc16_modbus

def test_crc16_known():
    # 這不是唯一測法：至少要確保穩定一致
    assert crc16_modbus(b"123456789") == 0x4B37
```

## 6.2 tests/test_framer.py（半包/黏包/雜訊）
```python
from core.framer import Framer
from core.crc16 import crc16_modbus, crc16_bytes_le

HEADER = bytes.fromhex("AA55")

def pack(payload: bytes) -> bytes:
    body = HEADER + bytes([len(payload)]) + payload
    crc = crc16_modbus(body)
    return body + crc16_bytes_le(crc)

def test_half_packet():
    f = Framer(HEADER)
    p = pack(b"\x01\x02hello")
    a, b = p[:3], p[3:]
    assert f.feed(a) == []
    out = f.feed(b)
    assert len(out) == 1 and out[0].ok

def test_sticky_packets():
    f = Framer(HEADER)
    p1 = pack(b"\x01\x02")
    p2 = pack(b"\x03\x04abcd")
    out = f.feed(p1 + p2)
    assert len(out) == 2 and all(x.ok for x in out)

def test_noise_resync():
    f = Framer(HEADER)
    noise = b"\x00\x11\x22\x33"
    p = pack(b"\x01\x02zz")
    out = f.feed(noise + p)
    assert len(out) == 1 and out[0].ok
```

跑測試：
```bash
pytest -q
```

---

# 7) Tier2 怎麼跑（建議流程）
1) 先用 FakeTransport：確認 UI 不會卡、節流正常  
2) 用 TCP echo server（你 Tier1 已有）：確認 readyRead + framer 解析正常  
3) 最後再接 Serial 真設備：看錯誤/重連策略是否如預期

---

# 8) 你做到 Tier2，實務上已經能接 70% 工控上位機需求
因為大多數工控上位機的痛點就是：
- I/O 不穩（半包黏包/超時/斷線）
- UI 被刷爆
- 沒有重連策略
- 沒有 replay 重現

Tier2 做完，這些都被你「工程化」掉了。

---

# 9) 下一階（你回我 Tier3 就接著）
Tier3 會把多媒體真正接上來（Lv8 加深）：

- Camera Tab（顯示 USB Cam / RTSP）
- Display/Record/Process 三管線分離
- 丟幀策略 + fps 限制 + 低延遲
- 即時曲線（pyqtgraph 或 QtCharts）
- 影像與控制事件時間對齊（timestamp）

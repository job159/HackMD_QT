# Lv5｜I/O（Serial / TCP）：readyRead vs while 輪詢，差的是「工程等級」

Lv4 你會用 QTimer 了，但 Lv5 要把你拉回正確方向：  
**通訊 I/O 不要用 Timer 等，也不要用 while 讀。**  
在 Qt 裡，I/O 是典型的事件驅動：資料到 → `readyRead` 通知 → 你處理 buffer。

---

## Lv5 的教學意義（你在練什麼）

- 了解 I/O 為什麼是 GUI 最大坑：時間不可預測 + 容易阻塞。
- 釐清你問的重點：
  - `readyRead` 跟 while 讀本質差別？
  - 為什麼 QTimer 不能拿來等資料？
  - Windows Python 能不能「中斷」？readyRead 是不是中斷？
- 建立工控常用 I/O 架構：
  - Driver 層（收 bytes）
  - Buffer + Framing（拆包）
  - Protocol/Parser（解析）
  - UI（顯示與操作）
- 把「資料不會一次剛好一包」這件事講透，避免掉包與亂包。

---

## 先回答你問的兩題（很重要）

### 1) readyRead 跟 while 讀有什麼本質差別？

#### while 讀（polling / blocking）
- 你主動一直問：「有資料了嗎？」
- 常見寫法：
  - `while True: read()`
  - 或 `while bytes_available(): read()`

問題：
- 會吃 CPU（忙等）
- 很容易阻塞 UI thread（卡住 event loop）
- 延遲不可控（你輪詢週期決定延遲）
- 程式結構容易變成「一坨 while」難維護

#### readyRead（event-driven）
- OS buffer 有資料 → Qt 收到通知 → 發 signal `readyRead`
- 你只在「真的有資料」時被叫起來處理
- 沒資料時不耗 CPU
- UI event loop 繼續跑，畫面不卡

> 結論：readyRead 是工程等級的 I/O 方法；while 輪詢是低階、容易翻車的方法。

---

### 2) 為什麼 QTimer 不能拿來等資料？

QTimer 是「時間到就提醒」，不是「條件成立就通知」。

用 QTimer 等資料本質上是輪詢：
- 資料早到但晚處理 → 延遲增加
- 資料爆量 → 來不及處理 → buffer 堆積或掉包
- 若 timer 間隔小 → 吃 CPU、UI 也會抖

**正解**：用 I/O 事件（readyRead）。

---

## Windows / Python 真的能實現「中斷」嗎？readyRead 算中斷嗎？

- 應用層（Python/Qt）通常拿不到硬體中斷（那是 driver / kernel 層）
- `readyRead` 是 **事件回呼**：
  - OS 告訴 Qt：「這個 socket/serial 現在可讀」
  - Qt 在 event loop 裡呼叫你的 slot
- 工程效果像「中斷通知」，但不是 CPU 硬中斷

> 對你做上位機/工控：你不需要硬中斷，你需要的是「非阻塞 + 事件通知」，readyRead 就是正解。

---

# Lv5 的核心定錨（先背）

1. I/O 時間不可預測 → **UI thread 不可以阻塞等資料**
2. readyRead 只告訴你「有資料可讀」，不保證「是一包完整資料」
3. **必須做 buffer + framing**：一次可能半包、也可能兩包
4. while 只適合用在「拆 buffer」，不適合用來「等待」

---

# 範例區（Lv5：大量實戰 code，直接可套用）

下面以「TCP socket」與「Serial」各做一套。

---

## 範例 1｜QTcpSocket：最小可用 readyRead（示範概念）

```python
from PyQt6.QtCore import QObject
from PyQt6.QtNetwork import QTcpSocket

class TcpClient(QObject):
    def __init__(self):
        super().__init__()
        self.sock = QTcpSocket()
        self.sock.connected.connect(lambda: print("connected"))
        self.sock.disconnected.connect(lambda: print("disconnected"))
        self.sock.readyRead.connect(self.on_ready_read)

    def connect_to(self, ip: str, port: int):
        self.sock.connectToHost(ip, port)

    def on_ready_read(self):
        data = self.sock.readAll().data()
        print("rx bytes:", len(data))
```

**小解釋**
- `readyRead` 觸發時代表「有資料可以讀」
- `readAll()` 讀走目前 buffer 內全部資料
- 但不代表是完整一包（下一個範例才是工程正解）

---

## 範例 2｜TCP 的工程正解：buffer + \n framing（最常見）

假設協議是「每一包以 `\n` 結尾」。

```python
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QTcpSocket

class TcpLineClient(QObject):
    line_received = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self.sock = QTcpSocket()
        self.sock.readyRead.connect(self.on_ready_read)
        self._buf = bytearray()

    def connect_to(self, ip: str, port: int):
        self.sock.connectToHost(ip, port)

    def on_ready_read(self):
        self._buf += self.sock.readAll().data()

        while True:
            idx = self._buf.find(b"\n")
            if idx < 0:
                break

            line = bytes(self._buf[:idx]).rstrip(b"\r")
            del self._buf[:idx+1]
            self.line_received.emit(line)
```

**工程重點**
- while 只用在「拆 buffer」
- 即使一次來半包，你也不會解析錯
- 即使一次來兩包，你也會拆成兩次 emit

---

## 範例 3｜TCP 用「固定長度 Header」拆包（更常見於工控）

假設格式：
- 前 2 bytes：payload 長度（uint16 big-endian）
- 後面 N bytes：payload

```python
import struct
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QTcpSocket

class TcpLenClient(QObject):
    frame_received = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self.sock = QTcpSocket()
        self.sock.readyRead.connect(self.on_ready_read)
        self._buf = bytearray()

    def connect_to(self, ip: str, port: int):
        self.sock.connectToHost(ip, port)

    def on_ready_read(self):
        self._buf += self.sock.readAll().data()

        while True:
            if len(self._buf) < 2:
                return
            (n,) = struct.unpack(">H", self._buf[:2])
            if len(self._buf) < 2 + n:
                return

            payload = bytes(self._buf[2:2+n])
            del self._buf[:2+n]
            self.frame_received.emit(payload)
```

**工程重點**
- TCP 沒有封包邊界，你必須自己定義 framing
- 固定 header 是工控協議很常見的做法

---

## 範例 4｜QSerialPort：readyRead + buffer + framing（串口正解）

```python
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtSerialPort import QSerialPort

class SerialLineDriver(QObject):
    line_received = pyqtSignal(bytes)

    def __init__(self, port: str, baud: int = 115200):
        super().__init__()
        self.ser = QSerialPort()
        self.ser.setPortName(port)
        self.ser.setBaudRate(baud)
        self.ser.readyRead.connect(self.on_ready_read)
        self._buf = bytearray()

    def open(self) -> bool:
        return self.ser.open(QSerialPort.OpenModeFlag.ReadWrite)

    def on_ready_read(self):
        self._buf += self.ser.readAll().data()

        while True:
            idx = self._buf.find(b"\n")
            if idx < 0:
                break
            line = bytes(self._buf[:idx]).rstrip(b"\r")
            del self._buf[:idx+1]
            self.line_received.emit(line)

    def write_line(self, s: str):
        self.ser.write((s + "\n").encode("utf-8"))
```

---

## 範例 5｜串口：「二進位封包 + checksum」拆包（工控常見）

假設協議：
- Start = 0xAA 0x55
- Len = 1 byte
- Payload = Len bytes
- CRC8 = 1 byte（此處示意，不提供完整 CRC 實作）

```python
from PyQt6.QtCore import QObject, pyqtSignal

class FrameParser(QObject):
    frame = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self.buf = bytearray()

    def feed(self, raw: bytes):
        self.buf += raw
        while True:
            # 找 header
            i = self.buf.find(b"\xAA\x55")
            if i < 0:
                self.buf.clear()
                return
            if i > 0:
                del self.buf[:i]

            if len(self.buf) < 3:
                return

            length = self.buf[2]
            total = 2 + 1 + length + 1
            if len(self.buf) < total:
                return

            payload = bytes(self.buf[3:3+length])
            crc = self.buf[3+length]
            del self.buf[:total]

            # TODO: check crc
            self.frame.emit(payload)
```

**工程重點**
- 你要能「找 header」「丟掉雜訊」「等完整長度」
- 這就是 state machine/解析器的工作

---

## 範例 6｜UI + Driver + Parser 分層（工控上位機標準架構）

```python
# UI: 只顯示/輸入
# Driver: 收 bytes（readyRead）
# Parser: 拆包/解析成 dict
# Controller: 決策流程，更新 UI

# 你只要保持：UI 不直接 parse、Driver 不直接碰 UI
```

（這裡先給原則，完整組裝範例通常會很長，Lv6 我們會把 heavy 的解析丟 thread。）

---

## 範例 7｜常見錯誤：readyRead 內直接 while 等更多資料（會卡 UI）

```python
def on_ready_read():
    buf += sock.readAll().data()
    while len(buf) < 1000:
        # ❌ 錯：你在等資料，UI thread 會卡死
        pass
```

**正解**：不夠就 return，等下一次 readyRead 再進來。

---

## 範例 8｜常見錯誤：readyRead 內做重運算（UI 也會卡）

```python
def on_ready_read():
    raw = sock.readAll().data()
    # ❌ 錯：解析、影像處理、AI 推論塞這裡
    do_heavy_processing(raw)
```

**正解方向**
- readyRead 只做收集與拆包（快速）
- 重工作丟 thread（Lv6）

---

## Lv5 常見錯誤總整理（你避開就穩）

- 以為一次 readyRead 就是一包完整資料
- 在 UI thread 同步 read 等資料
- 用 QTimer 輪詢等資料
- 在 readyRead 內 while 忙等更多資料
- 在 readyRead 內做重運算（解析太慢、UI 卡）

---

## Lv5 小作業（你真的做一次就懂）

做一個「串口 log 工具」：

- 上方：ConnectPanel（port / baud）
- 中間：狀態 label
- 下方：log 區（QPlainTextEdit）
- Driver 用 readyRead 接收
- framing 用 `\n`（每行一筆）
- 每收到一行就 append 到 log

**進階加分**
- 改成固定 header+len 的二進位封包，練拆包

---

## Lv5 結尾：你真正學到的是什麼？

你學到的是「I/O 的工程真相」：

- I/O 是不確定的（不是你能控制的時間）
- GUI 必須事件驅動，不能等待
- readyRead 是你在上位機/工控最穩的 I/O 基礎
- buffer + framing 才能避免亂包、掉包

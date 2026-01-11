# Tier 4｜平台化擴展：全插件化（Driver/Parser/Processor/UI 模組）+ 測試/CI + 回放治理 專案教學.md
> 接續 Tier 3：你已經能做 I/O + 協議解析 + 多媒體 + 曲線，而且不卡  
> Tier 4 目標：把它做成 **「可長期維護、可多人協作、可快速加功能」的平台**  
> 覆蓋重點：**Lv9（架構/插件/依賴反轉/測試/CI/可觀測）** 加深，並把 Lv10 的 replay schema/版本治理往前推

---

## 0) Tier 4 你會做到什麼（工程驗收清單）
### ✅ 平台化（Platform）
- 核心平台只管：EventBus / FSM / Config / Replay / Metrics / UI 框架
- 變動點全部 plugin 化：
  - Transport plugins（Serial/TCP/UDP/MQTT…）
  - Protocol plugins（Framer/CRC/編解碼）
  - Parser plugins（payload→dict）
  - Processor plugins（AI/頻譜/特徵/異常）
  - Recorder plugins（影像/資料/DB）
  - UI plugins（Tab 擴充：Camera/Plot/Device/Alarm）

### ✅ 插件生命週期與 ABI
- 每個 plugin 有：
  - `PLUGIN_ABI`（相容性）
  - `PLUGIN_META`（名稱/版本/能力）
  - `create(config, bus)`（工廠）
  - `start()/stop()`（生命週期）
- 平台啟動時依 config 載入 plugins；平台關閉時統一 stop/release

### ✅ Replay schema 版本治理
- `data_schema` 版本
- 明確定義事件 types：raw/state/frame/parsed/metric/video
- replay 既可重放，也可當 regression fixture

### ✅ 測試與 CI
- Parser/Framer/FSM/Config Schema 都能跑 pytest
- 基本 lint（ruff/flake8）與 type check（可選 mypy）
- 目標：**每次 commit 都能自動驗證不破**

---

# 1) Tier 4 專案結構（平台化後的 tree）
> 你會看到專案更像「產品平台」而不是單一 GUI 程式。

```
qt_platform_app/
├─ app/
│  ├─ main.py
│  ├─ app_context.py              ✅（集中：bus/fsm/replay/metrics/config）
│  ├─ config/
│  │  ├─ config.json
│  │  └─ schema_v1.json           ✅（config schema）
│  ├─ core/
│  │  ├─ bus.py
│  │  ├─ fsm.py
│  │  ├─ replay.py
│  │  ├─ metrics.py
│  │  ├─ plugin_api.py            ✅（插件介面/生命週期）
│  │  ├─ plugin_loader.py         🔁（支援多類插件 + registry）
│  │  ├─ registry.py              ✅（插件註冊表/能力查詢）
│  │  └─ diagnostics.py           ✅（support bundle）
│  └─ ui/
│     ├─ main_window.py
│     └─ host_tabs.py             ✅（UI 插件掛載點）
├─ plugins/
│  ├─ transports/
│  │  ├─ serial_transport.py
│  │  └─ tcp_transport.py
│  ├─ protocols/
│  │  ├─ aa55_len_crc.py          ✅（Framer plugin）
│  │  └─ line_delim.py            ✅（Line framer）
│  ├─ parsers/
│  │  ├─ demo_parser.py
│  │  └─ modbus_parser.py         ✅（示意）
│  ├─ processors/
│  │  ├─ stats_processor.py       ✅（計算統計）
│  │  └─ anomaly_processor.py     ✅（示意）
│  ├─ recorders/
│  │  ├─ replay_recorder.py       ✅（把 bus events 記到 jsonl）
│  │  └─ image_recorder.py        ✅（Tier3 延伸）
│  └─ ui_tabs/
│     ├─ devices_tab.py
│     ├─ logs_tab.py
│     └─ camera_tab.py            ✅（選配）
├─ tests/
│  ├─ test_config_schema.py
│  ├─ test_protocol_aa55.py
│  ├─ test_fsm.py
│  └─ test_parser_demo.py
├─ tools/
│  ├─ run_echo_server.py
│  └─ release_check.py            ✅（本機 CI 腳本）
└─ pyproject.toml / requirements.txt
```

---

# 2) Tier 4 Plugin API（平台必備：統一介面）
## 2.1 app/core/plugin_api.py
```python
from dataclasses import dataclass
from typing import Any, Dict, Protocol, Optional

PLUGIN_ABI_REQUIRED = 1

@dataclass(frozen=True)
class PluginMeta:
    name: str
    version: str
    kind: str           # "transport" / "protocol" / "parser" / "processor" / "recorder" / "ui_tab"
    description: str = ""
    capabilities: tuple[str, ...] = ()

class Plugin(Protocol):
    meta: PluginMeta

    def start(self) -> None: ...
    def stop(self) -> None: ...

def require_abi(module) -> None:
    abi = getattr(module, "PLUGIN_ABI", None)
    if abi != PLUGIN_ABI_REQUIRED:
        raise RuntimeError(f"Plugin ABI mismatch: abi={abi} required={PLUGIN_ABI_REQUIRED}")
```

---

# 3) Plugin Loader + Registry（可查詢、可列出、可掛載 UI）
## 3.1 app/core/registry.py
```python
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class RegistryItem:
    kind: str
    name: str
    module_path: str

class PluginRegistry:
    def __init__(self):
        self.items: Dict[str, RegistryItem] = {}   # key = kind:name

    def register(self, kind: str, name: str, module_path: str):
        key = f"{kind}:{name}"
        self.items[key] = RegistryItem(kind, name, module_path)

    def find(self, kind: str, name: str):
        return self.items.get(f"{kind}:{name}")

    def list_kind(self, kind: str):
        return [v for v in self.items.values() if v.kind == kind]
```

> Tier4 建議：**你可以「手動註冊」或「自動掃描 plugins/ 目錄」**。  
> 初學先用手動，等專案大了再做掃描。

---

## 3.2 app/core/plugin_loader.py（create(config, bus, ctx)）
```python
import importlib
from app.core.plugin_api import require_abi

def load_plugin(module_path: str):
    mod = importlib.import_module(module_path)
    require_abi(mod)
    return mod

def create_plugin(module_path: str, config: dict, bus, ctx):
    mod = load_plugin(module_path)
    if not hasattr(mod, "create"):
        raise RuntimeError(f"{module_path} missing create()")
    return mod.create(config=config, bus=bus, ctx=ctx)
```

---

# 4) AppContext：平台中樞（bus/fsm/replay/metrics/config）
## 4.1 app/app_context.py
```python
import json
from dataclasses import dataclass
from app.core.bus import BUS
from app.core.fsm import ConnFSM
from app.core.metrics import Metrics
from app.core.replay import ReplayRecorder

@dataclass
class AppContext:
    cfg: dict
    bus: any
    fsm: ConnFSM
    metrics: Metrics
    recorder: ReplayRecorder | None

def load_config(path="app/config/config.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_context():
    cfg = load_config()
    fsm = ConnFSM()
    metrics = Metrics()

    rep_cfg = cfg.get("replay", {})
    recorder = None
    if rep_cfg.get("enabled", True):
        recorder = ReplayRecorder(rep_cfg.get("path", "replay.jsonl"))

    return AppContext(cfg=cfg, bus=BUS, fsm=fsm, metrics=metrics, recorder=recorder)
```

---

# 5) 平台資料流：把「管線」變成 plugin 組合
Tier2 你有 `transport→framer→parser` 的 pipeline。  
Tier4 把它拆成 plugin：

- transport plugin：吐 raw bytes
- protocol plugin：raw→frames
- parser plugin：frame→parsed
- processors：parsed→derived metrics/alarms
- recorder：訂閱 bus events 記錄

---

## 5.1 protocol plugin（AA55+LEN+CRC）
### plugins/protocols/aa55_len_crc.py
```python
from dataclasses import dataclass
from app.core.plugin_api import PluginMeta

PLUGIN_ABI = 1
PLUGIN_META = PluginMeta(
    name="aa55_len_crc",
    version="1.0.0",
    kind="protocol",
    description="AA55 + LEN(1) + PAYLOAD + CRC16(modbus)",
    capabilities=("framing", "crc16")
)

from app.core.crc16 import crc16_modbus, crc16_bytes_le

@dataclass
class Frame:
    payload: bytes
    ok: bool
    err: str | None = None

class ProtocolAA55:
    meta = PLUGIN_META

    def __init__(self, header_hex="AA55"):
        self.header = bytes.fromhex(header_hex)
        self.buf = bytearray()
        self.bad_crc = 0
        self.bad_header = 0

    def start(self): ...
    def stop(self): ...

    def feed(self, raw: bytes):
        self.buf += raw
        out = []
        while True:
            idx = self.buf.find(self.header)
            if idx < 0:
                if len(self.buf) > len(self.header)-1:
                    self.buf = self.buf[-(len(self.header)-1):]
                break
            if idx > 0:
                del self.buf[:idx]
                self.bad_header += 1

            if len(self.buf) < len(self.header)+1:
                break
            plen = self.buf[len(self.header)]
            total = len(self.header)+1+plen+2
            if len(self.buf) < total:
                break

            pkt = bytes(self.buf[:total])
            del self.buf[:total]

            body = pkt[:-2]
            crc_recv = pkt[-2] | (pkt[-1]<<8)
            crc_calc = crc16_modbus(body)
            if crc_recv != crc_calc:
                self.bad_crc += 1
                out.append(Frame(payload=b"", ok=False, err="CRC"))
                continue

            payload = pkt[len(self.header)+1:-2]
            out.append(Frame(payload=payload, ok=True))
        return out

def create(config: dict, bus, ctx):
    header_hex = config.get("header_hex", "AA55")
    return ProtocolAA55(header_hex=header_hex)
```

---

## 5.2 parser plugin（payload→dict）
### plugins/parsers/demo_parser.py
```python
from app.core.plugin_api import PluginMeta

PLUGIN_ABI = 1
PLUGIN_META = PluginMeta(
    name="demo_parser",
    version="1.0.0",
    kind="parser",
    description="payload[0]=dev_id payload[1]=status_code",
    capabilities=("parse",)
)

class DemoParser:
    meta = PLUGIN_META

    def start(self): ...
    def stop(self): ...

    def parse(self, payload: bytes) -> dict:
        dev_id = payload[0] if len(payload) > 0 else 0
        status = payload[1] if len(payload) > 1 else 255
        return {
            "dev_id": int(dev_id),
            "status_code": int(status),
            "payload_len": len(payload),
            "payload_head": payload[:8].hex(),
        }

def create(config: dict, bus, ctx):
    return DemoParser()
```

---

## 5.3 processor plugin（例：統計/異常）
### plugins/processors/stats_processor.py
```python
from app.core.plugin_api import PluginMeta

PLUGIN_ABI = 1
PLUGIN_META = PluginMeta(
    name="stats_processor",
    version="1.0.0",
    kind="processor",
    description="count status_code distribution",
    capabilities=("metrics",)
)

class StatsProcessor:
    meta = PLUGIN_META

    def __init__(self):
        self.count = {}
        self.total = 0

    def start(self): ...
    def stop(self): ...

    def on_parsed(self, d: dict):
        sc = d.get("status_code", -1)
        self.count[sc] = self.count.get(sc, 0) + 1
        self.total += 1
        if self.total % 50 == 0:
            return {"type": "metric", "status_dist": dict(self.count), "total": self.total}
        return None

def create(config: dict, bus, ctx):
    return StatsProcessor()
```

---

## 5.4 recorder plugin（把 bus 事件統一記到 replay.jsonl）
### plugins/recorders/replay_recorder.py
```python
from app.core.plugin_api import PluginMeta
from app.core.replay import ReplayRecorder

PLUGIN_ABI = 1
PLUGIN_META = PluginMeta(
    name="replay_recorder",
    version="1.0.0",
    kind="recorder",
    description="record bus events to jsonl",
    capabilities=("replay",)
)

class BusRecorder:
    meta = PLUGIN_META

    def __init__(self, bus, recorder: ReplayRecorder | None):
        self.bus = bus
        self.rec = recorder
        self._conns = []

    def start(self):
        if not self.rec:
            return
        self._conns.append(self.bus.raw.connect(lambda b: self.rec.record({"type":"raw","len":len(b)})))
        self._conns.append(self.bus.state.connect(lambda s: self.rec.record({"type":"state","state":s})))
        self._conns.append(self.bus.parsed.connect(lambda d: self.rec.record({"type":"parsed","data":d})))

    def stop(self):
        # PyQt connect 解除比較麻煩（需要保存 slot references）
        # Tier4：先用「程序結束自然釋放」策略；Tier5 再強化嚴謹 disconnect
        pass

def create(config: dict, bus, ctx):
    return BusRecorder(bus=bus, recorder=ctx.recorder)
```

---

# 6) 平台啟動：根據 config 載入一組 plugins，組裝 pipeline
## 6.1 app/config/config.json（示意）
```json
{
  "versions": { "plugin_abi": 1, "data_schema": 1 },
  "transport": { "module": "plugins.transports.tcp_transport", "config": { "host": "127.0.0.1", "port": 9009 } },
  "protocol":  { "module": "plugins.protocols.aa55_len_crc",  "config": { "header_hex": "AA55" } },
  "parser":    { "module": "plugins.parsers.demo_parser",     "config": {} },
  "processors": [
    { "module": "plugins.processors.stats_processor", "config": {} }
  ],
  "recorders": [
    { "module": "plugins.recorders.replay_recorder", "config": {} }
  ],
  "ui_tabs": [
    { "module": "plugins.ui_tabs.devices_tab", "config": {} },
    { "module": "plugins.ui_tabs.logs_tab",    "config": {} }
  ],
  "replay": { "enabled": true, "path": "replay.jsonl" }
}
```

---

## 6.2 app/core/pipeline.py（平台版：靠 plugin 組裝）
```python
from PyQt6.QtCore import QObject
from app.core.plugin_loader import create_plugin

class PlatformPipeline(QObject):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        cfg = ctx.cfg
        bus = ctx.bus

        # create core plugins
        self.transport = create_plugin(cfg["transport"]["module"], cfg["transport"].get("config", {}), bus, ctx)
        self.protocol  = create_plugin(cfg["protocol"]["module"],  cfg["protocol"].get("config", {}),  bus, ctx)
        self.parser    = create_plugin(cfg["parser"]["module"],    cfg["parser"].get("config", {}),    bus, ctx)

        self.processors = [create_plugin(p["module"], p.get("config", {}), bus, ctx) for p in cfg.get("processors", [])]
        self.recorders  = [create_plugin(r["module"], r.get("config", {}), bus, ctx) for r in cfg.get("recorders", [])]

        # wire events
        self.transport.rx.connect(bus.raw.emit)
        bus.raw.connect(self._on_raw)

        # parsed → processors
        bus.parsed.connect(self._on_parsed)

        # start plugins
        for x in [self.transport, self.protocol, self.parser, *self.processors, *self.recorders]:
            x.start()

    def _on_raw(self, raw: bytes):
        frames = self.protocol.feed(raw)
        for fr in frames:
            if not fr.ok:
                continue
            d = self.parser.parse(fr.payload)
            self.ctx.bus.parsed.emit(d)

    def _on_parsed(self, d: dict):
        for p in self.processors:
            out = getattr(p, "on_parsed", None)
            if out:
                r = out(d)
                if r:
                    self.ctx.bus.metrics.emit(r)

    def shutdown(self):
        for x in [*self.recorders, *self.processors, self.parser, self.protocol, self.transport]:
            try: x.stop()
            except: pass
        try: self.transport.close()
        except: pass
```

---

# 7) UI 插件：Tab 可插拔（平台只提供 Host）
## 7.1 app/ui/host_tabs.py（主程式固定，tab 由 plugins 掛載）
```python
from PyQt6.QtWidgets import QTabWidget
from app.core.plugin_loader import create_plugin

class HostTabs(QTabWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

        for item in ctx.cfg.get("ui_tabs", []):
            tab = create_plugin(item["module"], item.get("config", {}), ctx.bus, ctx)
            tab.start()
            self.addTab(tab.widget(), tab.meta.name)

    def shutdown(self):
        # Tier4：簡化版
        pass
```

---

## 7.2 plugins/ui_tabs/logs_tab.py（範例：Log tab）
```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit
from app.core.plugin_api import PluginMeta

PLUGIN_ABI = 1
PLUGIN_META = PluginMeta(name="Logs", version="1.0.0", kind="ui_tab", capabilities=("ui",))

class LogsTab:
    meta = PLUGIN_META

    def __init__(self, bus):
        self.bus = bus
        self.w = QWidget()
        lay = QVBoxLayout(self.w)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        lay.addWidget(self.text)

    def start(self):
        self.bus.log.connect(self.text.appendPlainText)

    def stop(self): ...

    def widget(self):
        return self.w

def create(config: dict, bus, ctx):
    return LogsTab(bus=bus)
```

---

# 8) Config Schema（避免現場 config 寫錯就炸）
Tier4 要求你做「Schema 驗證」。最小做法：
- 用 JSON Schema（或自己手寫 validator）

這裡示意 **最小手寫 validator**（你不想引入第三方時）。

## 8.1 tests/test_config_schema.py（示意）
```python
import json

def validate_cfg(cfg: dict):
    assert "transport" in cfg and "module" in cfg["transport"]
    assert "protocol"  in cfg and "module" in cfg["protocol"]
    assert "parser"    in cfg and "module" in cfg["parser"]
    assert isinstance(cfg.get("processors", []), list)
    assert isinstance(cfg.get("ui_tabs", []), list)

def test_cfg_ok():
    cfg = json.load(open("app/config/config.json", "r", encoding="utf-8"))
    validate_cfg(cfg)
```

---

# 9) CI（最小可用：本機 release_check.py）
## 9.1 tools/release_check.py
```python
import subprocess, sys

def run(cmd):
    print(">", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(r.returncode)

def main():
    run(["python", "-m", "pytest", "-q"])
    print("OK: tests passed")

if __name__ == "__main__":
    main()
```

> 你把這個腳本綁到你 git 的 pre-push hook 或 CI，就能做到「每次 commit 都不破」。

---

# 10) Tier4 你做到這裡，已經接近產品平台
因為你現在具備：
- 可替換的插件系統
- 可插拔 UI tabs
- 管線可組裝（transport/protocol/parser/processor/recorder）
- replay 記錄
- 測試/CI 基礎

接下來 Tier5 才是「運營級」：安全更新/回滾、插件隔離進程、簽名、support bundle 一鍵匯出、replay 進階、遠端維運。

---

# 11) 下一階（你回我 Tier5）
Tier5 會把 Lv10 做到真正可上線：

- updater（外部更新器）+ manifest/hash/signature
- rollback
- support bundle（zip：log/config/replay/crash/version）
- plugin process isolation（插件獨立進程，IPC）
- replay schema version + migration
- 遠端維運：health report、遠端拉取 bundle、遠端升級

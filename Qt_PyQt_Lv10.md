# Lv10｜產品級最終形：遠端更新、資料回放、版本治理、安全強化、腳本化自動化（把 Qt 上位機做成「可長期運營的平台」）

Lv1～Lv9 你已經能做出「穩、不卡、可插拔、可測試、可觀測」的工控/多媒體上位機。  
Lv10 是再往上一步：**把它變成能在現場長期跑、能遠端維護、能安全更新、能回放重現問題**的「運營級產品」。

這級你會把工程收斂成一個完整閉環：

> **Build（建置）→ Package（打包）→ Sign（簽名）→ Update（更新）→ Observe（觀測）→ Replay（回放）→ Fix（修正）→ 再更新**

---

## Lv10 先背 8 個定錨（運營級產品的骨架）

1. **版本治理**：版本號、相容性、插件 ABI、配置版本、資料格式版本
2. **遠端更新**：完整更新（full）+ 差分更新（delta）+ 回滾（rollback）
3. **簽名與完整性**：更新包必須簽名；本地必須驗證；避免被植入
4. **資料回放（Replay）**：把現場資料錄下來，離線重現（尤其 I/O、影像）
5. **診斷與支援**：一鍵匯出 log/配置/crash dump；最小化現場溝通成本
6. **腳本化自動化**：一鍵 build、測試、打包、簽名、發布、產出版本報告
7. **安全邊界**：權限分離、最小權限、沙盒/隔離、敏感資訊保護
8. **可靠性工程**：看門狗（UI 與後端）、斷電保護、檔案原子寫入、錯誤恢復策略

---

# Part A｜版本治理：不要只是「v1.0」—你要管理相容性

## 1) 版本號建議（SemVer + build metadata）
- `MAJOR.MINOR.PATCH`（例如 2.4.1）
  - MAJOR：破壞相容（介面、配置、資料格式大改）
  - MINOR：新增功能但相容
  - PATCH：修 bug
- build metadata：git sha、build time、平台

---

## 範例 1｜集中版本資訊（程式/插件/配置都要有）

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Versions:
    app: str = "2.4.1"
    plugin_abi: int = 3          # 插件介面版本（非常重要）
    config_schema: int = 5       # config.json 版本
    data_schema: int = 2         # frame/log/replay 格式版本
    git_sha: str = "abc1234"

VERS = Versions()

def about_text():
    return (
        f"MyApp v{VERS.app} (sha={VERS.git_sha})\n"
        f"plugin_abi={VERS.plugin_abi} config_schema={VERS.config_schema} data_schema={VERS.data_schema}"
    )
```

---

## 2) 插件 ABI 檢查：不相容就拒絕載入（避免現場炸）
每個 plugin 也要宣告 ABI：

```python
PLUGIN_ABI = 3

def create(config: dict):
    # ...
    return obj
```

載入時檢查：

```python
import importlib

def load_plugin(path: str, config: dict, required_abi: int):
    mod = importlib.import_module(path)
    if getattr(mod, "PLUGIN_ABI", None) != required_abi:
        raise RuntimeError(f"Plugin ABI mismatch: {path}")
    return mod.create(config)
```

---

# Part B｜遠端更新：要有「安全更新＋回滾」才敢放現場

你可以選兩條路：

1) **外部更新器（推薦）**：App 只負責下載/通知，更新器負責替換檔案（更安全、可回滾）
2) **App 自更新（較難）**：App 自己替換自己（Windows 特別麻煩，容易檔案鎖定）

> 工控現場最常用：**App + Updater（小工具）**，App 退出後 updater 做更新、再重啟 App。

---

## 更新包格式建議（可簡單也可嚴謹）

- `manifest.json`：版本、檔案列表、hash、大小、相容性
- `payload/`：實際檔案（exe/dll/plugins/resources）
- `signature.sig`：對 manifest 的簽名（或對整包簽）

---

## 範例 2｜manifest.json（概念）

```json
{
  "app": "2.4.1",
  "min_app": "2.3.0",
  "plugin_abi": 3,
  "files": [
    { "path": "MyApp.exe", "sha256": "..." },
    { "path": "plugins/serial_transport.py", "sha256": "..." }
  ],
  "notes": "Fix reconnect bug; improve logging"
}
```

---

## 範例 3｜檔案 hash 計算（sha256）

```python
import hashlib, pathlib

def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
```

---

## 範例 4｜原子更新（Atomic replace）+ 回滾（Windows/Linux 通用概念）

更新器策略：
1. 下載到 `staging/`
2. 驗證簽名 + hash
3. 把舊版本移到 `backup/`
4. 把新版本搬到 `current/`
5. 若失敗 → rollback（把 backup 還原）

示意（概念 code）：

```python
import shutil, pathlib

def atomic_update(current: pathlib.Path, staging: pathlib.Path, backup: pathlib.Path):
    if backup.exists():
        shutil.rmtree(backup)
    current.rename(backup)              # move current → backup
    staging.rename(current)             # move staging → current
```

> 真實工程：要考慮 exe 正在跑會鎖檔 → 所以 updater 通常在 app 退出後才做。

---

# Part C｜簽名與完整性：更新包一定要驗證（安全核心）

最基本要做到兩件事：
1) **hash 完整性**：檔案沒被改
2) **signature 真偽**：更新包是你發布的，不是攻擊者做的

---

## 範例 5｜使用 Ed25519 做簽名（概念）
（這裡示意流程，不綁死某個套件；實務你可用 libsodium/cryptography）

- 發布端：用私鑰簽 `manifest.json`
- 客戶端：用內建公鑰驗 `signature.sig`

流程：
- `sig = Sign(private_key, SHA256(manifest_bytes))`
- `Verify(public_key, SHA256(manifest_bytes), sig)`

### 工程意義
- 更新站被入侵也不怕（沒有私鑰就簽不過）
- 你能把「信任」鎖死在 app 內的公鑰

---

## 範例 6｜把公鑰硬編在程式（概念）

```python
PUBLIC_KEY_B64 = "..."  # 編譯時注入或寫死
```

---

# Part D｜Replay（資料回放）：現場問題最強解法

你做工控/串流，最痛的是：
- 現場說「有時候會卡」
- 你沒資料、沒辦法重現
- 只能猜

Replay 的目標是：
- 把「輸入」錄下來（raw bytes / frames / events）
- 離線重跑同一套 parser/fsm/processor
- 重現 bug → 修 → 回歸測試

---

## 1) 最小 Replay 格式（建議 JSONL 或自訂二進位）

### JSONL（每行一筆）
- 好處：人可讀、好 debug
- 壞處：大流量/影像不適合（太大）

範例（每行）：

```json
{"ts": 1730000000.123, "type": "raw", "source": "tcp:192.168.1.10:502", "b64": "AAEC..."}
```

---

## 範例 7｜錄 raw bytes（base64）到 jsonl

```python
import base64, json, time

def record_raw(fp, source: str, payload: bytes):
    rec = {
        "ts": time.time(),
        "type": "raw",
        "source": source,
        "b64": base64.b64encode(payload).decode("ascii")
    }
    fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    fp.flush()
```

---

## 範例 8｜回放：把 jsonl 餵回 parser（重現）

```python
import base64, json, time

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

            feed_fn(raw)  # 送回 parser/framer
```

**工程意義**
- 你可以離線「重跑一遍現場資料」
- parser/fsm 的 bug 一次抓乾淨
- 也能做 regression test（把 jsonl 放進測試用資料夾）

---

## 2) 影像 replay（建議）
- 影像建議不要 JSONL；可以：
  - 只記「關鍵幀」或降低解析度/帧率
  - 或直接錄成 mp4（同時記 timestamp）
- 你要把「影像」與「控制事件」做時間對齊（用 ts）

---

# Part E｜支援能力：一鍵匯出診斷包（Support Bundle）

現場最需要的是：
- 不要叫使用者複製一堆檔案
- 一鍵產出 zip：包含 log、config、版本、crash report、最近 replay

---

## 範例 9｜打包 support bundle（概念）

```python
import zipfile, pathlib, time

def make_bundle(out_zip: str, paths: list[str]):
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            pth = pathlib.Path(p)
            if pth.exists():
                z.write(pth, arcname=pth.name)

bundle = f"support_{int(time.time())}.zip"
make_bundle(bundle, ["config.json", "app.log", "crash_reports/latest.txt"])
```

---

# Part F｜腳本化自動化：一鍵 build/test/package/sign/release

你到 Lv10，所有流程都要腳本化，避免人工出錯。

你可以做一個 `tools/release.py`：
- 讀版本
- 跑測試
- 打包
- 產 manifest
- 算 hash
- 簽名
- 產出 release artifacts
- 生成 release notes（可從 git log）

---

## 範例 10｜最小 release pipeline（概念）

```python
import subprocess, sys

def run(cmd):
    print(">", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(r.returncode)

def main():
    run(["python", "-m", "pytest", "-q"])
    run(["python", "-m", "PyInstaller", "myapp.spec"])
    # TODO: generate manifest + hashes
    # TODO: sign manifest
    # TODO: upload artifacts (internal server / S3)

if __name__ == "__main__":
    main()
```

---

# Part G｜安全強化：最小權限、沙盒、敏感資訊保護

工控上位機常見安全坑：

- 把 token/password 寫在明文 config
- log 印出敏感資訊
- plugin 可以任意 import/執行（等於任意碼執行）
- 更新包未簽名（供應鏈攻擊）

---

## 1) 敏感資訊策略（可落地）
- config 分兩份：
  - `config.json`（非敏感）
  - `secrets.json`（敏感，權限限制）
- 或使用 OS 的安全儲存（Windows Credential Manager / Linux keyring）

---

## 2) plugin 安全邊界（可逐步做到）
- 嚴謹做法：插件跑在 **獨立進程**（IPC 通訊）
- 好處：插件炸了不拖垮主程式；也能限制權限
- 你可以用：
  - `QProcess` 啟動 plugin service
  - `QLocalSocket` / TCP / ZeroMQ（看你需求）傳消息

---

## 範例 11｜插件獨立進程（概念骨架）

```python
from PyQt6.QtCore import QProcess

proc = QProcess()
proc.start("plugin_service.exe", ["--mode", "parser"])
```

主程式只跟它用 IPC 交換 frame/result。  
（這個架構會大幅提升穩定性與安全性。）

---

# Part H｜可靠性工程：斷電、檔案、崩潰與自復原

## 1) 檔案原子寫入（避免斷電寫壞）
- 寫到 temp
- fsync
- rename 覆蓋

（Python 可用 `pathlib` + `os.replace`。）

---

## 範例 12｜原子寫 config（概念）

```python
import os, json, pathlib, tempfile

def atomic_write_json(path: str, obj: dict):
    p = pathlib.Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)  # atomic replace on most OS
```

---

## 2) 兩層看門狗（Watchdog）
- UI 看後端：後端心跳超時 → UI 提示、重連、降級
- 後端看 UI：UI 長時間不回應 → 重啟（可由 updater/守護進程做）

---

# Lv10 常見錯誤（產品做不久的原因）

- 沒有回放：現場問題永遠只能猜
- 沒有簽名：更新一旦被劫持就完蛋
- 沒有回滾：更新失敗只能派人去現場
- 沒有一鍵診斷包：support 成本超高
- 流程不腳本化：release 常常出人為錯誤
- 插件沒隔離：一個插件 bug 會拖垮整個系統

---

# Lv10 小作業（做完你就是「能運營」的等級）

做一個「運營級上位機骨架」：

1. `Versions`：app/plugin_abi/config_schema/data_schema
2. Plugin loader：ABI 檢查，不相容拒絕載入
3. Replay：
   - 連線時錄 raw bytes（jsonl）
   - 提供回放模式：讀 jsonl 餵 parser/fsm
4. Support bundle：
   - 一鍵匯出 zip（log/config/version/crash/replay）
5. Update（先做 mock）：
   - 讀 manifest
   - 驗 sha256
   - 驗 signature（可以先假裝）
   - staging → current + rollback
6. Release script：
   - pytest → build → package → manifest → sign（流程跑通）

---

## Lv10 結尾：你真正學到的是什麼？

Lv10 讓你跨過「會寫 GUI」到「會做產品」的門檻：

- 你能安全更新、能回滾
- 你能錄資料、能回放重現
- 你能一鍵產出診斷包，support 成本極低
- 你能腳本化 release，品質可控
- 你能把插件隔離，穩定性與安全性上升一個量級

如果你願意，我可以把 Lv1～Lv10 整理成：
- 一份「完整課程型 Markdown」  
- 一個「可跑的範例專案骨架」（含 plugins、event bus、fsm、replay、bundle、updater stub）

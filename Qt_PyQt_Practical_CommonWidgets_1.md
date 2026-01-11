|
# Qt / PyQt 實戰（10 單元）— 單元 1：元件大展演 + 上位機骨架（可直接跑）

> 你說「元件使用方法太少」，所以我把單元 1 做成 **「元件展示 + 真的像上位機的骨架」**：  
> 你跑起來會看到：左側參數面板、上方工具列、右側狀態區、下方狀態列、中央 Log、分頁(Tab)、分割器(Splitter)、快捷鍵、驗證器、對話框…  
> 後面單元才會逐步把 **I/O、Thread、Model/View、FSM、影像**等專案化。

---

## 全系列 10 單元（案件導向）

1. **單元 1｜元件大展演 + 上位機骨架（可直接跑）**（本檔）
2. 單元 2｜參數面板做成「可交付工具」：Validator / 提示 / 依賴關係 / 表單配置
3. 單元 3｜I/O 監看器：Serial / TCP（readyRead + buffer + framing + 解析接口）
4. 單元 4｜Log 系統：分級、限行數、搜尋、匯出、Copy、可觀測性
5. 單元 5｜長任務不卡：QThread + Worker + 可停止 + 進度 + 取消
6. 單元 6｜大量資料不卡：QTableView + QAbstractTableModel + Proxy(排序/搜尋/過濾)
7. 單元 7｜流程不爆：連線/重連/握手/超時 → FSM（QStateMachine / 清楚 FSM）
8. 單元 8｜設定保存：QSettings（參數、視窗狀態、欄寬、最近檔案）
9. 單元 9｜影像 / 即時可視化：OpenCV / Camera + 丟幀策略 + 節流刷新
10. 單元 10｜產品化閉環：打包、版本資訊、Crash log、Replay（最小可用）

---

# 單元 1 要達成什麼？

## ✅ 你會同時學到兩件事

1) **上位機骨架**（UI 不會寫成一坨）  
- View（UI）只收輸入 / 顯示  
- Controller 負責流程（後面單元會加 I/O、FSM、Thread）  

2) **大量元件使用方法**（這單元就是展示給你看）  
你會看到並且用到這些元件：

- Layout：`QVBoxLayout / QHBoxLayout / QFormLayout / QGridLayout`
- 表單輸入：`QLineEdit / QSpinBox / QDoubleSpinBox / QComboBox / QCheckBox / QRadioButton`
- 顯示：`QLabel / QProgressBar / QPlainTextEdit`
- 結構：`QGroupBox / QTabWidget / QSplitter`
- 導航/操作：`QMainWindow / QMenuBar / QToolBar / QAction / QStatusBar`
- 互動：`QMessageBox / QFileDialog`
- 工程：`QTimer（節流刷新）/ QShortcut（快捷鍵）/ QValidator（輸入驗證）/ QCompleter（輸入提示）`

---

# 單元 1：直接給你「可跑的完整範例」

> 你先把這份存成 `unit01_demo.py`，然後：  
> `python unit01_demo.py`（或用 VS Code 直接 Run）

> 需要：`pip install PyQt6`

```python
import sys
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, QRegularExpression
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QRadioButton,
    QGroupBox, QTabWidget, QSplitter, QProgressBar,
    QMessageBox, QFileDialog, QStatusBar, QToolBar, QCompleter
)


# ---------------------------
# 1) 一個「乾淨」的資料模型（UI 不要到處傳散亂的 dict）
# ---------------------------
@dataclass
class ConnConfig:
    host: str
    port: int
    proto: str             # "TCP" / "Serial"（先做 UI 示範）
    auto_reconnect: bool
    timeout_ms: int


# ---------------------------
# 2) Controller：先做最小版（單元 3 才會接真 I/O）
# ---------------------------
class Controller:
    def __init__(self, ui_log_append, ui_set_status):
        self.ui_log_append = ui_log_append
        self.ui_set_status = ui_set_status
        self._connected = False

    def connect(self, cfg: ConnConfig):
        self.ui_log_append(f"[CTRL] connect request: {cfg}")
        self.ui_set_status("Connecting ...")
        QTimer.singleShot(250, lambda: self._finish_connect(cfg))

    def _finish_connect(self, cfg: ConnConfig):
        self._connected = True
        self.ui_set_status("Connected ✅")
        self.ui_log_append(f"[CTRL] connected ({cfg.proto}) to {cfg.host}:{cfg.port}")

    def disconnect(self):
        self.ui_log_append("[CTRL] disconnect")
        self._connected = False
        self.ui_set_status("Disconnected")

    def send(self, text: str):
        if not self._connected:
            self.ui_log_append("[WARN] not connected, cannot send")
            return
        self.ui_log_append(f"[TX] {text}")


# ---------------------------
# 3) MainWindow：元件大展演
# ---------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unit01 - Widget Showcase + SCADA Skeleton (PyQt6)")
        self.resize(1100, 720)

        # ============ Central Widget + Splitter ============
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)

        mid_panel = self._build_mid_panel()
        splitter.addWidget(mid_panel)

        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([320, 600, 260])

        # ============ StatusBar ============
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_label = QLabel("Disconnected")
        sb.addPermanentWidget(self.status_label)

        # ============ Toolbar + Menu ============
        self._build_actions()

        # ============ Controller ============
        self.ctrl = Controller(ui_log_append=self.append_log, ui_set_status=self.set_status)

        # ============ Timer：示範「節流刷新 / 心跳」 ============
        self.heartbeat = QTimer(self)
        self.heartbeat.setInterval(1000)
        self.heartbeat.timeout.connect(self._on_heartbeat)
        self.heartbeat.start()

        # ============ 快捷鍵（QShortcut） ============
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.clear_log)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.fake_alarm)

        self.append_log("[SYS] started. (Ctrl+L 清 log / Ctrl+K 模擬告警)")

    # ---------------------------
    # UI：左側參數面板
    # ---------------------------
    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        gb_conn = QGroupBox("連線設定（FormLayout）")
        form = QFormLayout(gb_conn)

        self.edit_host = QLineEdit("127.0.0.1")
        completer = QCompleter(["127.0.0.1", "192.168.1.10", "broker.emqx.io", "test.mosquitto.org"])
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.edit_host.setCompleter(completer)

        host_re = QRegularExpression(r"^([a-zA-Z0-9\-\.]{1,253}|\d{1,3}(\.\d{1,3}){3})$")
        self.edit_host.setValidator(QRegularExpressionValidator(host_re))

        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(1883)
        self.spin_port.setSuffix(" 端口")

        self.combo_proto = QComboBox()
        self.combo_proto.addItems(["TCP", "Serial"])

        self.chk_reconn = QCheckBox("自動重連")
        self.chk_reconn.setChecked(True)

        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(50, 60_000)
        self.spin_timeout.setValue(2000)
        self.spin_timeout.setSingleStep(100)
        self.spin_timeout.setSuffix(" ms")

        form.addRow("Host / IP", self.edit_host)
        form.addRow("Port", self.spin_port)
        form.addRow("Protocol", self.combo_proto)
        form.addRow("", self.chk_reconn)
        form.addRow("Timeout", self.spin_timeout)
        layout.addWidget(gb_conn)

        gb_ctrl = QGroupBox("控制參數（GridLayout）")
        grid = QGridLayout(gb_ctrl)

        self.spin_rate = QDoubleSpinBox()
        self.spin_rate.setRange(0.1, 100.0)
        self.spin_rate.setDecimals(1)
        self.spin_rate.setValue(10.0)
        self.spin_rate.setSuffix(" Hz")

        self.spin_gain = QDoubleSpinBox()
        self.spin_gain.setRange(0.0, 999.0)
        self.spin_gain.setDecimals(2)
        self.spin_gain.setValue(1.00)

        self.radio_mode_a = QRadioButton("Mode A")
        self.radio_mode_b = QRadioButton("Mode B")
        self.radio_mode_a.setChecked(True)

        self.chk_verbose = QCheckBox("Verbose log")
        self.chk_verbose.setChecked(False)

        grid.addWidget(QLabel("Update Rate"), 0, 0)
        grid.addWidget(self.spin_rate, 0, 1)
        grid.addWidget(QLabel("Gain"), 1, 0)
        grid.addWidget(self.spin_gain, 1, 1)

        grid.addWidget(QLabel("Mode"), 2, 0)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.radio_mode_a)
        mode_row.addWidget(self.radio_mode_b)
        mode_wrap = QWidget()
        mode_wrap.setLayout(mode_row)
        grid.addWidget(mode_wrap, 2, 1)

        grid.addWidget(self.chk_verbose, 3, 0, 1, 2)

        layout.addWidget(gb_ctrl)

        btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_disconnect)
        layout.addLayout(btn_row)

        gb_tx = QGroupBox("發送（returnPressed）")
        tx_layout = QVBoxLayout(gb_tx)
        self.edit_tx = QLineEdit()
        self.edit_tx.setPlaceholderText("輸入要送的文字，按 Enter 送出")
        tx_layout.addWidget(self.edit_tx)
        layout.addWidget(gb_tx)

        self.btn_connect.clicked.connect(self.on_connect_clicked)
        self.btn_disconnect.clicked.connect(self.on_disconnect_clicked)
        self.edit_tx.returnPressed.connect(self.on_tx_enter)

        layout.addStretch(1)
        return w

    # ---------------------------
    # UI：中間面板（Tabs + Log）
    # ---------------------------
    def _build_mid_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        tab_console = QWidget()
        v = QVBoxLayout(tab_console)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Log 會顯示在這裡（Ctrl+L 清除）")
        v.addWidget(self.log)

        search_row = QHBoxLayout()
        self.edit_find = QLineEdit()
        self.edit_find.setPlaceholderText("搜尋關鍵字（示範用）")
        btn_find = QPushButton("Find Next")
        btn_copy = QPushButton("Copy All")
        btn_save = QPushButton("Export Log")
        search_row.addWidget(self.edit_find)
        search_row.addWidget(btn_find)
        search_row.addWidget(btn_copy)
        search_row.addWidget(btn_save)
        v.addLayout(search_row)

        btn_find.clicked.connect(self.find_next)
        btn_copy.clicked.connect(self.copy_all_log)
        btn_save.clicked.connect(self.export_log)

        self.tabs.addTab(tab_console, "Console")

        tab_mon = QWidget()
        g = QGridLayout(tab_mon)

        self.lbl_rssi = QLabel("-- dBm")
        self.lbl_rssi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_rate = QLabel("-- Hz")
        self.lbl_rate.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pb_load = QProgressBar()
        self.pb_load.setRange(0, 100)
        self.pb_load.setValue(0)

        g.addWidget(QLabel("RSSI"), 0, 0)
        g.addWidget(self.lbl_rssi, 0, 1)
        g.addWidget(QLabel("Update Rate"), 1, 0)
        g.addWidget(self.lbl_rate, 1, 1)
        g.addWidget(QLabel("CPU Load (fake)"), 2, 0)
        g.addWidget(self.pb_load, 2, 1)

        self.tabs.addTab(tab_mon, "Monitor")

        return w

    # ---------------------------
    # UI：右側狀態面板
    # ---------------------------
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        gb = QGroupBox("狀態面板")
        v = QVBoxLayout(gb)

        self.lbl_state = QLabel("Disconnected")
        self.lbl_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_state.setStyleSheet("font-size: 16px; font-weight: 600;")

        self.lbl_hint = QLabel("提示：Ctrl+L 清 log\nCtrl+K 模擬告警")
        self.lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        v.addWidget(self.lbl_state)
        v.addWidget(self.lbl_hint)
        layout.addWidget(gb)

        gb_tools = QGroupBox("常用對話框示範")
        vv = QVBoxLayout(gb_tools)
        btn_info = QPushButton("Show Info")
        btn_confirm = QPushButton("Ask Confirm")
        btn_open = QPushButton("Open File ...")
        vv.addWidget(btn_info)
        vv.addWidget(btn_confirm)
        vv.addWidget(btn_open)
        layout.addWidget(gb_tools)

        btn_info.clicked.connect(self.show_info)
        btn_confirm.clicked.connect(self.ask_confirm)
        btn_open.clicked.connect(self.open_file_dialog)

        layout.addStretch(1)
        return w

    # ---------------------------
    # Menu / Toolbar / Actions
    # ---------------------------
    def _build_actions(self):
        act_connect = QAction("Connect", self)
        act_connect.setShortcut(QKeySequence("Ctrl+Enter"))

        act_disconnect = QAction("Disconnect", self)

        act_clear = QAction("Clear Log", self)
        act_clear.setShortcut(QKeySequence("Ctrl+L"))

        act_about = QAction("About", self)

        act_connect.triggered.connect(self.on_connect_clicked)
        act_disconnect.triggered.connect(self.on_disconnect_clicked)
        act_clear.triggered.connect(self.clear_log)
        act_about.triggered.connect(self.show_about)

        m_file = self.menuBar().addMenu("File")
        m_file.addAction(act_connect)
        m_file.addAction(act_disconnect)
        m_file.addSeparator()
        m_file.addAction("Exit", self.close)

        m_view = self.menuBar().addMenu("View")
        m_view.addAction(act_clear)

        m_help = self.menuBar().addMenu("Help")
        m_help.addAction(act_about)

        tb = QToolBar("Main")
        self.addToolBar(tb)
        tb.addAction(act_connect)
        tb.addAction(act_disconnect)
        tb.addAction(act_clear)

    # ---------------------------
    # Event handlers
    # ---------------------------
    def on_connect_clicked(self):
        cfg = ConnConfig(
            host=self.edit_host.text().strip(),
            port=int(self.spin_port.value()),
            proto=self.combo_proto.currentText(),
            auto_reconnect=self.chk_reconn.isChecked(),
            timeout_ms=int(self.spin_timeout.value()),
        )

        if cfg.proto == "Serial":
            self.append_log("[UI] Serial 模式目前只示範 UI，單元 3 才接 QSerialPort。")

        mode = "A" if self.radio_mode_a.isChecked() else "B"
        self.append_log(f"[UI] mode={mode}, rate={self.spin_rate.value():.1f}Hz, gain={self.spin_gain.value():.2f}")

        self.ctrl.connect(cfg)

    def on_disconnect_clicked(self):
        self.ctrl.disconnect()

    def on_tx_enter(self):
        text = self.edit_tx.text().strip()
        if not text:
            return
        self.ctrl.send(text)
        self.edit_tx.clear()

    # ---------------------------
    # Log helpers
    # ---------------------------
    def append_log(self, line: str):
        MAX_LINES = 2000
        self.log.appendPlainText(line)

        while self.log.blockCount() > MAX_LINES:
            cursor = self.log.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def clear_log(self):
        self.log.clear()
        self.append_log("[SYS] log cleared.")

    def copy_all_log(self):
        QApplication.clipboard().setText(self.log.toPlainText())
        self.set_status("Copied log ✅")

    def export_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Log", "log.txt", "Text Files (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.log.toPlainText())
        self.append_log(f"[SYS] log exported: {path}")

    def find_next(self):
        key = self.edit_find.text().strip()
        if not key:
            return
        text = self.log.toPlainText()
        cur = self.log.textCursor()
        start = cur.position()
        idx = text.find(key, start + 1)
        if idx < 0:
            idx = text.find(key, 0)
        if idx >= 0:
            cur.setPosition(idx)
            cur.setPosition(idx + len(key), cur.MoveMode.KeepAnchor)
            self.log.setTextCursor(cur)
            self.set_status(f"Found: {key}")
        else:
            self.set_status("Not Found")

    # ---------------------------
    # Status & misc
    # ---------------------------
    def set_status(self, s: str):
        self.status_label.setText(s)
        self.lbl_state.setText(s)

        if "Connected" in s:
            self.lbl_state.setStyleSheet("font-size: 16px; font-weight: 700; color: green;")
        elif "Error" in s or "WARN" in s:
            self.lbl_state.setStyleSheet("font-size: 16px; font-weight: 700; color: red;")
        else:
            self.lbl_state.setStyleSheet("font-size: 16px; font-weight: 600;")

    def _on_heartbeat(self):
        self.lbl_rate.setText(f"{self.spin_rate.value():.1f} Hz")
        v = self.pb_load.value()
        self.pb_load.setValue((v + 7) % 101)
        fake = -50 - (self.pb_load.value() // 5)
        self.lbl_rssi.setText(f"{fake} dBm")

    def fake_alarm(self):
        self.append_log("[ALARM] OverTemp (fake)")
        QMessageBox.warning(self, "Alarm", "OverTemp (fake)\n（單元 7 會變成真正狀態機 + 告警系統）")

    def show_info(self):
        QMessageBox.information(self, "Info", "這是 QMessageBox.information 示範。")

    def ask_confirm(self):
        ret = QMessageBox.question(self, "Confirm", "要清除 log 嗎？")
        if ret == QMessageBox.StandardButton.Yes:
            self.clear_log()

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*.*)")
        if path:
            self.append_log(f"[UI] open file: {path}")

    def show_about(self):
        QMessageBox.information(self, "About", "Unit01：元件展示 + 上位機骨架（PyQt6）")


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

```

---

# 你在這單元「應該學會」的元件用法重點（快速複盤）

## A) `QLineEdit`（Host/IP）實戰要點
- `setPlaceholderText()`：提示用法
- `setCompleter()`：常用值補全
- `setValidator()`：避免亂輸  
  - 本單元用 `QRegularExpressionValidator` 做簡易 host/IP 限制

## B) `QSpinBox / QDoubleSpinBox`（比 LineEdit 適合數值）
- `setRange(min,max)`：防呆第一步  
- `setSuffix(" ms")`：讓使用者知道單位  
- `setDecimals()`：控制小數位數（DoubleSpinBox）

## C) `QComboBox`（模式/協議）
- `addItems([...])`：一次填入
- `currentText()`：讀出選項

## D) `QCheckBox / QRadioButton`（狀態與模式）
- `isChecked()`：讀狀態
- 用 `RadioButton` 表達互斥模式（A/B）

## E) `QGroupBox + Layout`（讓介面像產品）
- `QFormLayout`：左 label 右輸入（最常見）
- `QGridLayout`：儀表 / 多欄布局
- `QSplitter`：可拖拉區塊（上位機常用）
- `QTabWidget`：同窗多頁（Console / Monitor）

## F) `QMainWindow`（工具列 + 狀態列）
- `menuBar()` + `QAction`：功能入口
- `QToolBar`：常用按鈕
- `QStatusBar`：顯示狀態（Connected/Copy/Found…）

## G) 對話框（一定會用）
- `QMessageBox.information / warning / question`
- `QFileDialog.getOpenFileName / getSaveFileName`

## H) 工程級加分
- `QTimer`：節流刷新、心跳監測（允許抖動）
- `QShortcut`：Ctrl+L 清 log、Ctrl+K 告警
- Log 限行數：避免「跑久了就卡」

---

# 下一單元預告（單元 2）

單元 2 我會把「參數面板」做成真的可以交付給客戶/現場用的等級：  
- IP/Port 驗證更完整（包含 IPv4 每段 0~255）
- 欄位依賴（選 TCP/Serial → 顯示不同欄位）
- 錯誤提示（紅框 + tooltip）
- 預設值與「套用/還原」按鈕
- 每個元件的「事件觸發策略」：textChanged vs editingFinished vs currentIndexChanged


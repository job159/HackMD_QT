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
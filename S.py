import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QGridLayout

app = QApplication(sys.argv)

panel = QWidget()
grid = QGridLayout(panel)

keys = [
    ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
    ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
    ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
    ("0", 3, 1),
    ("+", 4, 0), ("-", 4, 2),
]

def on_click(text):
    print(text)

for text, r, c in keys:
    btn = QPushButton(text)
    btn.clicked.connect(lambda checked, t=text: on_click(t))
    grid.addWidget(btn, r, c)

panel.show()

sys.exit(app.exec())

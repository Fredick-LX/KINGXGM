import os
import sys
from pathlib import Path
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtWebEngineWidgets import *

class L2DView(QWebEngineView):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowOpacity(0)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.page().setBackgroundColor(Qt.transparent)
        data_dir = Path(os.path.abspath(os.path.dirname(__file__)))
        url = QUrl.fromLocalFile(f"{data_dir}/main2.html")
        self.load(url)

class MainWindow(QMainWindow):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent)
        self.l2d_view = L2DView(self)
        self.context_menu_init()
        self.win_init()

    def context_menu_init(self):
        self.context_menu = QMenu(self)

    def win_init(self):
        win_width = 200
        win_height = 300
        scr_width = QApplication.desktop().width()
        scr_height = QApplication.desktop().height()
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(win_width, win_height)
        self.move(scr_width - win_width, scr_height - win_height)
        self.setCentralWidget(self.l2d_view)
    def win_reload(self):
        self.l2d_view.reload()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

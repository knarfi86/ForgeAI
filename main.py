# main.py

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ForgeAI")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        button = QPushButton("Start Project")
        button.clicked.connect(self.start_project)
        layout.addWidget(button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def start_project(self):
        print("Project started!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

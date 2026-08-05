import sys

from PySide6.QtWidgets import QApplication

from forgeai.app import ForgeAIApplication


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ForgeAI")

    application = ForgeAIApplication(app)
    application.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
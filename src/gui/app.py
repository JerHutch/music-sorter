import sys
from PySide6.QtWidgets import QApplication
from src.core.config import Config
from src.core.logging_setup import setup_logging
from src.gui.main_window import MainWindow


def main():
    config = Config.load_user_config()
    setup_logging(config)
    app = QApplication(sys.argv)
    app.setApplicationName("Music Sorter")
    app.setOrganizationName("MusicSorter")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

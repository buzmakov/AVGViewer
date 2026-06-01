from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    if len(sys.argv) > 1:
        avg_path = Path(sys.argv[1])
        if avg_path.exists():
            window.open_avg(avg_path)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

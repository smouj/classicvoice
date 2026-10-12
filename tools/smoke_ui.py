from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from classicvoice.app import ClassicVoiceApp  # noqa: E402


def main() -> int:
    app = ClassicVoiceApp()
    app.withdraw()
    app.after(50, app._close)
    app.mainloop()
    print("Tkinter UI startup/close: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

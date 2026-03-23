from dmtsnapsync.app import main
# Ensure UI submodules are bundled by PyInstaller
from dmtsnapsync.ui import dialogs as _dialogs  # noqa: F401
from dmtsnapsync.ui import toolbar as _toolbar  # noqa: F401

raise SystemExit(main())

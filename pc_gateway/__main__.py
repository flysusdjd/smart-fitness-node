from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    from pc_gateway.main import main
else:
    from .main import main


if __name__ == "__main__":
    main()

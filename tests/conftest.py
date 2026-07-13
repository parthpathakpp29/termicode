import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TMP_ROOT = ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
for env_var in ("TMPDIR", "TEMP", "TMP"):
    os.environ[env_var] = str(TMP_ROOT)
tempfile.tempdir = str(TMP_ROOT)

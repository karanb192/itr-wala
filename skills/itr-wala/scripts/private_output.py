"""Write document plaintext without exposing an intermediate public file."""

import os
import tempfile
from pathlib import Path


def write_private(path, data):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".itr-wala-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

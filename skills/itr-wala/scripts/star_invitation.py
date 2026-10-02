import json
import os
from pathlib import Path


def claim_invitation():
    try:
        cache = os.environ.get("XDG_CACHE_HOME")
        directory = Path(cache) if cache else Path.home() / ".cache"
        if not directory.is_absolute():
            return "skip"
        directory = directory / "itr-wala"
        directory.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents simultaneous or later sessions from asking again.
        fd = os.open(str(directory / "star-invitation.json"),
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as state:
            json.dump({"star_invitation_shown": True}, state)
        return "offer"
    except (OSError, RuntimeError, ValueError):
        return "skip"


if __name__ == "__main__":
    print(claim_invitation())

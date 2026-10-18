"""Browser support (pygbag / WebAssembly build).

In the browser the game runs on an in-memory file system that is wiped when
the page reloads.  Every save file is therefore mirrored into the page's
localStorage (base64) and restored into the file system at start-up.  On
desktop all of this is a no-op.
"""
import base64
import os
import sys

from . import config as C

WEB = sys.platform == "emscripten"
PREFIX = "pyraria:"


def _storage():
    try:
        import platform           # pygbag's bridge to the browser
        return platform.window.localStorage
    except Exception:             # pragma: no cover - desktop / no storage
        return None


def _key(path):
    rel = os.path.relpath(os.path.abspath(path), C.SAVE_DIR)
    return PREFIX + rel.replace(os.sep, "/")


def persist(path):
    """Copy a just-written save file into browser storage."""
    if not WEB:
        return True
    ls = _storage()
    if ls is None:
        return False
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        ls.setItem(_key(path), data)
        return True
    except Exception as e:        # quota exceeded, etc.
        print(f"[webstore] could not persist {path}: {e}")
        return False


def forget(path):
    if not WEB:
        return
    ls = _storage()
    if ls is not None:
        try:
            ls.removeItem(_key(path))
        except Exception:
            pass


def restore_all():
    """Recreate every stored save file in the in-memory file system."""
    if not WEB:
        return 0
    ls = _storage()
    if ls is None:
        return 0
    restored = 0
    try:
        keys = [ls.key(i) for i in range(int(ls.length))]
    except Exception:
        return 0
    for key in keys:
        if not key or not str(key).startswith(PREFIX):
            continue
        rel = str(key)[len(PREFIX):]
        if ".." in rel.split("/"):
            continue
        try:
            data = base64.b64decode(str(ls.getItem(key)))
            path = os.path.join(C.SAVE_DIR, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            restored += 1
        except Exception as e:
            print(f"[webstore] could not restore {key}: {e}")
    return restored

"""Own the private X display that IceWM runs on, and the IceWM process itself.

The display, capture, and input injection are *not* implemented here. Kilix
already owns that machinery in ``kilix_sdk.xapp.XAppSession`` -- a private
authenticated Xvfb, XDamage capture with a polling fallback, RandR refit when
the pane resizes, and XTest injection of the kitty keyboard/mouse protocols.
Reimplementing any of it would mean a second copy of the hardest code in the
stack drifting against the first.

What is genuinely this provider's own problem is the part below: deciding
*what* to run on that display, writing IceWM a private configuration so it
never reads or writes the operator's ``~/.icewm``, and supervising the window
manager so its death is reported rather than leaving a black pane.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time

__all__ = ["IceWMConfig", "IceWMProcess", "resolve_icewm"]

# IceWM's own default; overridden per-launch so a crashed session cannot leave
# the operator's real configuration half-written.
CONFIG_FILES = ("menu", "toolbar", "preferences", "keys")


def resolve_icewm(prefix: str | None = None, env=None):
    """Find the icewm binaries to run, preferring our built prefix.

    Returns ``(session_binary, wm_binary)``. The session binary starts the full
    desktop (window manager, taskbar, background); the plain wm binary is the
    fallback when only that got built.
    """
    env = os.environ if env is None else env
    candidates = []
    if prefix:
        candidates.append(os.path.join(prefix, "bin"))
    extra = env.get("KILIX_ICEWM_PREFIX")
    if extra:
        candidates.append(os.path.join(extra, "bin"))

    def find(name):
        for d in candidates:
            p = os.path.join(d, name)
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        return shutil.which(name)

    return find("icewm-session"), find("icewm")


class IceWMConfig:
    """A private IceWM configuration directory written fresh each launch."""

    def __init__(self, root: str):
        self.root = root

    def write(self, files: dict) -> str:
        """Write ``{name: text}`` into the private config dir, 0700/0600.

        Unknown names are rejected rather than written: this path takes
        generated content, and a stray key would let a caller drop an arbitrary
        file into a directory IceWM executes hooks from.
        """
        os.makedirs(self.root, mode=0o700, exist_ok=True)
        os.chmod(self.root, 0o700)
        written = []
        for name, text in files.items():
            if name not in CONFIG_FILES:
                raise ValueError(f"refusing to write unknown icewm config: {name!r}")
            path = os.path.join(self.root, name)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)          # atomic: never a half-read menu
            written.append(path)
        return self.root

    def env_for(self, base=None) -> dict:
        """Environment that points IceWM at this private directory."""
        env = dict(os.environ if base is None else base)
        env["ICEWM_PRIVCFG"] = self.root
        # IceWM consults XDG_CONFIG_HOME/icewm before its builtin default; both
        # are redirected so nothing reaches the operator's real dotfiles.
        env["XDG_CONFIG_HOME"] = os.path.dirname(self.root.rstrip("/")) or self.root
        return env


class IceWMProcess:
    """Supervise one IceWM instance on an already-running private display."""

    def __init__(self, binary: str, display: str, env=None, xauthority=None):
        if not binary:
            raise ValueError("no icewm binary to run")
        self.binary = binary
        self.display = display
        self.env = dict(env or os.environ)
        self.env["DISPLAY"] = display
        if xauthority:
            self.env["XAUTHORITY"] = xauthority
        self.proc = None

    def start(self):
        self.proc = subprocess.Popen(
            [self.binary],
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,        # a stray Ctrl-C in the pane is ours, not IceWM's
        )
        return self.proc

    def poll(self):
        return None if self.proc is None else self.proc.poll()

    def failure_text(self, limit: int = 2000) -> str:
        """Whatever IceWM said before dying, bounded.

        Without this a failed window manager shows up as an unexplained black
        pane; IceWM's own stderr is almost always the actual diagnosis.
        """
        if self.proc is None or self.proc.stderr is None:
            return ""
        try:
            text = self.proc.stderr.read(limit).decode("utf-8", "replace").strip()
        except Exception:
            return ""
        if self.proc.poll() is not None:
            self._close_stderr()
        return text

    def stop(self, timeout: float = 3.0) -> None:
        """Ask the session to end, then insist. Never leaves a zombie WM
        holding the private display open."""
        if self.proc is None:
            return
        if self.proc.poll() is not None:
            self._close_stderr()
            return
        try:
            self._stop_running(timeout)
        finally:
            self._close_stderr()

    def _stop_running(self, timeout: float) -> None:
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try:
                self.proc.terminate()
            except ProcessLookupError:
                return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                return                     # graceful exit: the common path
            time.sleep(0.05)
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass
        try:
            self.proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:  # pragma: no cover - kill raced
            pass
        finally:
            self._close_stderr()

    def _close_stderr(self) -> None:
        """Release the stderr pipe. Relaunching the desktop repeatedly in one
        session would otherwise leak one descriptor per launch."""
        if self.proc is not None and self.proc.stderr is not None:
            try:
                self.proc.stderr.close()
            except Exception:
                pass

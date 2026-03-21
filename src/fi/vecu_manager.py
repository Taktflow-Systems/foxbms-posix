"""vECU and plant model process management.

Manages starting, stopping, and restarting the foxbms-vecu binary
and plant_model.py processes for fault injection testing.
"""

import os
import signal
import subprocess
import time
from typing import Optional


class VecuManager:
    """Manages the foxbms-vecu and plant_model.py processes."""

    def __init__(self, interface: str, vecu_path: str, plant_path: str):
        self.interface = interface
        self.vecu_path = vecu_path
        self.plant_path = plant_path
        self.vecu_proc: Optional[subprocess.Popen] = None
        self.plant_proc: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        """Start vECU + plant model. Returns True on success."""
        self.stop()

        print(f"[runner] Starting plant_model.py on {self.interface}...")
        self.plant_proc = subprocess.Popen(
            ["python3", self.plant_path, self.interface],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )

        time.sleep(0.5)  # Let plant settle and send initial data

        print(f"[runner] Starting foxbms-vecu on {self.interface}...")
        env = os.environ.copy()
        env["FOXBMS_CAN_IF"] = self.interface
        self.vecu_proc = subprocess.Popen(
            [self.vecu_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
            env=env,
        )

        return self.vecu_proc.poll() is None and self.plant_proc.poll() is None

    def stop(self) -> None:
        """Stop both processes."""
        for proc, name in [(self.vecu_proc, "vecu"), (self.plant_proc, "plant")]:
            if proc and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        proc.wait(timeout=2)
                    except (ProcessLookupError, subprocess.TimeoutExpired):
                        pass
                print(f"[runner] Stopped {name} (pid={proc.pid})")
        self.vecu_proc = None
        self.plant_proc = None

    def is_alive(self) -> bool:
        """Check if both processes are still running."""
        if self.vecu_proc is None or self.plant_proc is None:
            return False
        return self.vecu_proc.poll() is None and self.plant_proc.poll() is None

    def restart(self) -> bool:
        """Restart both processes."""
        print("[runner] Restarting vECU + plant...")
        return self.start()

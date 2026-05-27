#!/usr/bin/env python3
"""Start Flask for Lighthouse CI testing in test mode."""
import os
import socket
import subprocess
import sys
import time


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def main() -> None:
    port = 5000
    
    # Set environment
    env = os.environ.copy()
    env["TEST_MODE"] = "1"
    env["GOOGLE_CLIENT_ID"] = "dummy"
    env["GOOGLE_CLIENT_SECRET"] = "dummy"
    
    print(f"Starting Flask on port {port}...", flush=True)
    
    # Start Flask server
    proc = subprocess.Popen(
        ["uv", "run", "flask", "--app", "book_lamp.app:app", "run", "--port", str(port), "--host", "127.0.0.1"],
        env=env,
    )
    
    # Wait for port to be ready
    for _ in range(60):
        if is_port_open(port):
            print(f"Server ready at http://127.0.0.1:{port}", flush=True)
            break
        time.sleep(1)
    else:
        print("Server failed to start", file=sys.stderr)
        proc.kill()
        sys.exit(1)
    
    # Wait for process to end
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.kill()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
RunPod SSH Wrapper: Handle PTY allocation issues on Windows

Problem: Git Bash's bundled SSH client cannot allocate PTY from non-terminal contexts,
causing "Your SSH client doesn't support PTY" errors on Windows when connecting to
RunPod (which requires PTY).

Solution: Use Windows-native OpenSSH (System32) which properly supports PTY allocation
via -tt flag with stdin piping, without requiring an interactive terminal.

This wrapper is NOT Claude Code specific — it solves a fundamental Windows SSH issue
that affects ANY tool (bash scripts, Python, Rust, etc.) running on Windows WSL/Git Bash.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def convert_bash_path_to_windows(bash_path: str) -> str:
    """
    Convert Git Bash path format to Windows path format.
    Examples:
      /c/Users/sneak/.ssh/id_ed25519 -> C:\\Users\\sneak\\.ssh\\id_ed25519
      /d/data/keys -> D:\\data\\keys
      C:\\Users\\... -> C:\\Users\\... (already Windows, pass through)
    """
    # Already Windows format
    if ":\\" in bash_path:
        return bash_path

    # Convert /c/... or /d/... format
    if bash_path.startswith("/") and len(bash_path) > 2 and bash_path[2] == "/":
        drive_letter = bash_path[1].upper()
        rest = bash_path[3:].replace("/", "\\")
        return f"{drive_letter}:\\{rest}"

    return bash_path


def run_ssh_command(
    ssh_key: str,
    ssh_user: str,
    ssh_host: str,
    ssh_port: int,
    command: str,
    timeout: int = 30,
) -> tuple[int, str]:
    """
    Execute a command on the remote RunPod pod via SSH.

    Args:
        ssh_key: Path to SSH private key (supports Git Bash or Windows format)
        ssh_user: SSH username (e.g., pod-id-sessiontoken)
        ssh_host: SSH host (e.g., ssh.runpod.io)
        ssh_port: SSH port (default 22)
        command: Command to execute on the remote pod
        timeout: Command timeout in seconds

    Returns:
        Tuple of (exit_code, output)
    """
    # Validate inputs
    ssh_key_path = Path(ssh_key).expanduser()
    if not ssh_key_path.exists():
        return 1, f"SSH key not found: {ssh_key}"

    # Use Windows-native OpenSSH if on Windows
    if platform.system() == "Windows" or "MSYS" in os.environ or "GIT_BASH" in os.environ:
        return _run_ssh_windows_native(
            str(ssh_key_path), ssh_user, ssh_host, ssh_port, command, timeout
        )

    # Fall back to system SSH on Unix-like systems
    return _run_ssh_unix(ssh_key, ssh_user, ssh_host, ssh_port, command, timeout)


def _run_ssh_windows_native(
    ssh_key: str, ssh_user: str, ssh_host: str, ssh_port: int, command: str, timeout: int
) -> tuple[int, str]:
    """
    Execute SSH using Windows-native OpenSSH from System32.

    Why Windows-native?
    - Git Bash's bundled ssh cannot allocate PTY without an interactive terminal
    - System32's OpenSSH supports -tt (force PTY) and works with stdin piping
    - Bypasses the "Your SSH client doesn't support PTY" error entirely
    """
    # Convert key path to Windows format (System32 ssh.exe needs backslashes)
    key_path_windows = convert_bash_path_to_windows(ssh_key)

    # Build SSH command using Windows-native ssh.exe
    ssh_exe = r"C:\Windows\System32\OpenSSH\ssh.exe"
    if not Path(ssh_exe).exists():
        return 1, (
            f"Windows OpenSSH not found at {ssh_exe}. "
            "Install via: Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0"
        )

    # Critical: Use -tt (double-t) to force PTY allocation
    # Pipe the command through stdin via printf (RunPod ignores exec-mode args)
    ssh_cmd = [
        ssh_exe,
        "-tt",  # Force PTY allocation (this is the key fix!)
        "-i",
        key_path_windows,
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=NUL",  # Windows-native: NUL not /dev/null
        "-o",
        "LogLevel=ERROR",
        "-p",
        str(ssh_port),
        f"{ssh_user}@{ssh_host}",
    ]

    # Build the input command with exit to close the session
    ssh_input = f"{command} 2>&1\nexit\n"

    try:
        # Set MSYS_NO_PATHCONV=1 to prevent Git Bash from mangling Windows paths
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"

        result = subprocess.run(
            ssh_cmd,
            input=ssh_input,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )

        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, f"SSH command timed out after {timeout}s"
    except Exception as e:
        return 1, f"SSH error: {e}"


def _run_ssh_unix(
    ssh_key: str, ssh_user: str, ssh_host: str, ssh_port: int, command: str, timeout: int
) -> tuple[int, str]:
    """
    Execute SSH using the system SSH (Unix/Linux/macOS).
    Works fine on Unix because PTY allocation is straightforward.
    """
    ssh_cmd = [
        "ssh",
        "-T",  # Disable PTY (Unix can handle this; RunPod adapts)
        "-i",
        ssh_key,
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "LogLevel=ERROR",
        "-p",
        str(ssh_port),
        f"{ssh_user}@{ssh_host}",
        command,
    ]

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, f"SSH command timed out after {timeout}s"
    except Exception as e:
        return 1, f"SSH error: {e}"


def main():
    """CLI entry point for direct usage."""
    if len(sys.argv) < 2:
        print("Usage: runpod-ssh-wrapper.py <command> [--key PATH] [--user USER] [--host HOST] [--port PORT]")
        print("")
        print("Example:")
        print("  runpod-ssh-wrapper.py 'supervisorctl status' --key ~/.ssh/id_ed25519 --user pod-id-token --host ssh.runpod.io --port 22")
        sys.exit(1)

    # Parse args (simple parsing for script usage)
    command = sys.argv[1]
    ssh_key = os.environ.get("RUNPOD_SSH_KEY", os.path.expanduser("~/.ssh/id_ed25519"))
    ssh_user = os.environ.get("RUNPOD_SSH_USER", "")
    ssh_host = os.environ.get("RUNPOD_SSH_HOST", "ssh.runpod.io")
    ssh_port = int(os.environ.get("RUNPOD_SSH_PORT", "22"))

    # Override from command-line args
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--key" and i + 1 < len(sys.argv):
            ssh_key = sys.argv[i + 1]
        elif arg == "--user" and i + 1 < len(sys.argv):
            ssh_user = sys.argv[i + 1]
        elif arg == "--host" and i + 1 < len(sys.argv):
            ssh_host = sys.argv[i + 1]
        elif arg == "--port" and i + 1 < len(sys.argv):
            ssh_port = int(sys.argv[i + 1])

    if not ssh_user:
        print("ERROR: RUNPOD_SSH_USER is not set. Set it via environment or --user flag.", file=sys.stderr)
        sys.exit(1)

    exit_code, output = run_ssh_command(ssh_key, ssh_user, ssh_host, ssh_port, command)
    print(output, end="")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

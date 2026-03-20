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


def run_scp_command(
    ssh_key: str,
    ssh_user: str,
    ssh_host: str,
    ssh_port: int,
    local_path: str,
    remote_path: str,
) -> tuple[int, str]:
    """
    Copy a local file or directory to the remote RunPod pod via SCP.

    Args:
        local_path: Local source path (supports Git Bash format on Windows)
        remote_path: Absolute destination path on the remote pod (e.g. /model/)
    """
    ssh_key_path = Path(ssh_key).expanduser()
    if not ssh_key_path.exists():
        return 1, f"SSH key not found: {ssh_key}"

    if platform.system() == "Windows" or "MSYS" in os.environ or "GIT_BASH" in os.environ:
        return _run_scp_windows_native(
            str(ssh_key_path), ssh_user, ssh_host, ssh_port, local_path, remote_path
        )

    return _run_scp_unix(ssh_key, ssh_user, ssh_host, ssh_port, local_path, remote_path)


def _run_scp_windows_native(
    ssh_key: str,
    ssh_user: str,
    ssh_host: str,
    ssh_port: int,
    local_path: str,
    remote_path: str,
) -> tuple[int, str]:
    """Copy files using Windows-native scp.exe from System32."""
    scp_exe = r"C:\Windows\System32\OpenSSH\scp.exe"
    if not Path(scp_exe).exists():
        return 1, (
            f"Windows OpenSSH scp not found at {scp_exe}. "
            "Install via: Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0"
        )

    key_path_windows = convert_bash_path_to_windows(ssh_key)
    local_path_windows = convert_bash_path_to_windows(local_path)
    remote_target = f"{ssh_user}@{ssh_host}:{remote_path}"

    scp_cmd = [
        scp_exe,
        "-r",
        "-i", key_path_windows,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-o", "LogLevel=ERROR",
        "-P", str(ssh_port),
        local_path_windows,
        remote_target,
    ]

    try:
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        result = subprocess.run(
            scp_cmd,
            text=True,
            capture_output=True,
            timeout=120,
            env=env,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "SCP timed out after 120s"
    except Exception as e:
        return 1, f"SCP error: {e}"


def _run_scp_unix(
    ssh_key: str,
    ssh_user: str,
    ssh_host: str,
    ssh_port: int,
    local_path: str,
    remote_path: str,
) -> tuple[int, str]:
    """Copy files using system scp on Unix/Linux/macOS."""
    remote_target = f"{ssh_user}@{ssh_host}:{remote_path}"

    scp_cmd = [
        "scp",
        "-r",
        "-i", ssh_key,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        "-P", str(ssh_port),
        local_path,
        remote_target,
    ]

    try:
        result = subprocess.run(
            scp_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "SCP timed out after 120s"
    except Exception as e:
        return 1, f"SCP error: {e}"


def _parse_connection_args(args: list[str], start: int) -> dict:
    """Parse --key, --user, --host, --port from args starting at index."""
    result = {
        "ssh_key": os.environ.get("RUNPOD_SSH_KEY", os.path.expanduser("~/.ssh/id_ed25519")),
        "ssh_user": os.environ.get("RUNPOD_SSH_USER", ""),
        "ssh_host": os.environ.get("RUNPOD_SSH_HOST", "ssh.runpod.io"),
        "ssh_port": int(os.environ.get("RUNPOD_SSH_PORT", "22")),
    }
    i = start
    while i < len(args):
        if args[i] == "--key" and i + 1 < len(args):
            result["ssh_key"] = args[i + 1]
            i += 2
        elif args[i] == "--user" and i + 1 < len(args):
            result["ssh_user"] = args[i + 1]
            i += 2
        elif args[i] == "--host" and i + 1 < len(args):
            result["ssh_host"] = args[i + 1]
            i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            result["ssh_port"] = int(args[i + 1])
            i += 2
        else:
            i += 1
    return result


def main():
    """CLI entry point for direct usage."""
    if len(sys.argv) < 2:
        print("Usage: runpod-ssh-wrapper.py <command> [--key PATH] [--user USER] [--host HOST] [--port PORT]")
        print("       runpod-ssh-wrapper.py scp <local-path> <remote-path> [--key PATH] ...")
        sys.exit(1)

    subcommand = sys.argv[1]

    if subcommand == "scp":
        # scp mode: runpod-ssh-wrapper.py scp <local> <remote> [--key ...] [--user ...] ...
        if len(sys.argv) < 4:
            print("Usage: runpod-ssh-wrapper.py scp <local-path> <remote-path> [--key PATH] ...", file=sys.stderr)
            sys.exit(1)
        local_path = sys.argv[2]
        remote_path = sys.argv[3]
        conn = _parse_connection_args(sys.argv, 4)
        if not conn["ssh_user"]:
            print("ERROR: RUNPOD_SSH_USER is not set.", file=sys.stderr)
            sys.exit(1)
        exit_code, output = run_scp_command(
            conn["ssh_key"], conn["ssh_user"], conn["ssh_host"], conn["ssh_port"],
            local_path, remote_path,
        )
        print(output, end="")
        sys.exit(exit_code)

    # ssh mode (original behavior): runpod-ssh-wrapper.py <command> [--key ...] ...
    command = subcommand
    conn = _parse_connection_args(sys.argv, 2)

    if not conn["ssh_user"]:
        print("ERROR: RUNPOD_SSH_USER is not set. Set it via environment or --user flag.", file=sys.stderr)
        sys.exit(1)

    exit_code, output = run_ssh_command(
        conn["ssh_key"], conn["ssh_user"], conn["ssh_host"], conn["ssh_port"], command
    )
    print(output, end="")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

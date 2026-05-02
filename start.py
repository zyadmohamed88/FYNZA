import os
import subprocess
import sys
import time
import webbrowser
import threading

def get_python():
    """Always use venv Python if available (has torch/flask installed)."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(base_dir, "env1", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable

def stream_logs(process, prefix):
    """Read output from process and print with a prefix."""
    try:
        for line in iter(process.stdout.readline, b''):
            if line:
                print(f"{prefix} {line.decode('utf-8', errors='replace').rstrip()}")
    except Exception as e:
        print(f"{prefix} Error reading logs: {e}")

def main():
    print("===================================================")
    print("    Starting StegoCrypt Full-Stack Application")
    print("===================================================\n")

    # Paths to our directories
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")

    python_exe = get_python()
    print(f"[*] Using Python: {python_exe}")

    # Start Backend (Flask API)
    print("[*] Starting Backend (Flask API) on port 5000...")
    backend_process = subprocess.Popen(
        [python_exe, "-u", "app.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    # Start Frontend (HTTP Server)
    print("[*] Starting Frontend (HTTP Server) on port 8000...")
    frontend_process = subprocess.Popen(
        [sys.executable, "-u", "-m", "http.server", "8000"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    # Start threads to stream logs
    threading.Thread(target=stream_logs, args=(backend_process, "[BACKEND]"), daemon=True).start()
    threading.Thread(target=stream_logs, args=(frontend_process, "[FRONTEND]"), daemon=True).start()

    print("\n[*] Waiting for servers to initialize...")
    time.sleep(3)

    print("[*] Opening browser to http://localhost:8000 ...")
    webbrowser.open("http://localhost:8000")

    print("\n===================================================")
    print("[OK] StegoCrypt is now running!")
    print("[!]  Press Ctrl+C in this terminal to stop both servers.")
    print("===================================================\n")

    try:
        # Keep the script running to keep the child processes alive
        while True:
            time.sleep(1)
            # If backend or frontend crashes, we should probably know
            if backend_process.poll() is not None:
                print("\n[!] Backend process has stopped unexpectedly.")
                break
            if frontend_process.poll() is not None:
                print("\n[!] Frontend process has stopped unexpectedly.")
                break
    except KeyboardInterrupt:
        print("\n\n[!] Stopping servers gracefully...")
    finally:
        backend_process.terminate()
        frontend_process.terminate()
        backend_process.wait()
        frontend_process.wait()
        print("[OK] Servers stopped successfully. Goodbye!")

if __name__ == "__main__":
    main()

import os
import signal
import subprocess
import sys
import threading
import time


PYTHON = sys.executable


def build_web_command():
    use_gunicorn = os.name != "nt" and os.getenv("USE_GUNICORN", "1") == "1"
    if use_gunicorn:
        workers = os.getenv("WEB_CONCURRENCY", "1")
        return [
            "gunicorn",
            "app:app",
            "--bind",
            f"0.0.0.0:{os.getenv('PORT', '5000')}",
            "--workers",
            workers,
        ]
    return [PYTHON, "app.py"]


def build_agent_command():
    agent_mode = os.getenv("AGENT_MODE", "dev")
    return [PYTHON, "agent.py", agent_mode]


def stream_output(name, process):
    assert process.stdout is not None
    for line in iter(process.stdout.readline, ""):
        if not line:
            break
        print(f"[{name}] {line.rstrip()}", flush=True)


def terminate_process(name, process):
    if process.poll() is not None:
        return

    print(f"Stopping {name}...", flush=True)
    try:
        if os.name == "nt":
            process.terminate()
        else:
            process.send_signal(signal.SIGTERM)
    except Exception:
        pass


def main():
    commands = {
        "web": build_web_command(),
        "agent": build_agent_command(),
    }

    processes = {}
    threads = []

    try:
        for name, command in commands.items():
            print(f"Starting {name}: {' '.join(command)}", flush=True)
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            processes[name] = process
            thread = threading.Thread(target=stream_output, args=(name, process), daemon=True)
            thread.start()
            threads.append(thread)

        while True:
            for name, process in processes.items():
                return_code = process.poll()
                if return_code is not None:
                    print(f"{name} exited with code {return_code}. Stopping remaining processes.", flush=True)
                    for other_name, other_process in processes.items():
                        if other_name != name:
                            terminate_process(other_name, other_process)
                    time.sleep(1)
                    sys.exit(return_code)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutdown requested.", flush=True)
        for name, process in processes.items():
            terminate_process(name, process)
        time.sleep(1)
    finally:
        for thread in threads:
            thread.join(timeout=1)


if __name__ == "__main__":
    main()

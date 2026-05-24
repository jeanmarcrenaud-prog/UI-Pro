import subprocess


def kill_port(port):
    try:
        # Find process using the port
        result = subprocess.run(
            f"netstat -ano | findstr :{port}",
            shell=True,
            capture_output=True,
            text=True,
        )
        lines = result.stdout.strip().split("\n")
        pids = set()
        for line in lines:
            if (line and "LISTENING" in line.upper()) or "ESTABLISHED" in line.upper():
                parts = line.split()
                if len(parts) >= 5:
                    pids.add(parts[-1])

        for pid in pids:
            try:
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                print(f"Killed PID {pid}")
            except:
                pass
    except:
        pass


if __name__ == "__main__":
    kill_port(8000)
    print("Port 8000 cleared")

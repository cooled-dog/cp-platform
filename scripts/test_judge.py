import subprocess, tempfile, os, time

code = r"""
#include <iostream>
int main() {
    int a, b;
    std::cin >> a >> b;
    std::cout << a + b << std::endl;
    return 0;
}
"""

tmpdir = tempfile.mkdtemp()
print(f"Working in {tmpdir}")

with open(f"{tmpdir}/solution.cpp", "w") as f:
    f.write(code)

# compile
print("\n--- Compiling ---")
compile_result = subprocess.run([
    "docker", "run", "--rm",
    "--network", "none",
    "-v", f"{tmpdir}:/sandbox",
    "gcc:13",
    "sh", "-c", "g++ -O2 -o /sandbox/solution /sandbox/solution.cpp 2>&1"
], capture_output=True, text=True)

print("Return code:", compile_result.returncode)
print("Output:", compile_result.stdout + compile_result.stderr)

if compile_result.returncode != 0:
    print("VERDICT: CE")
    exit()

# write input to a file instead of using stdin pipe
input_data = "3 4\n"
input_file = f"{tmpdir}/input.txt"
with open(input_file, "w") as f:
    f.write(input_data)

print("\n--- Running ---")
start = time.monotonic()

try:
    run_result = subprocess.run([
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "256m",
        "--cpus", "0.5",
        "--pids-limit", "50",
        "-v", f"{tmpdir}:/sandbox",   # removed :ro so input file is readable
        "gcc:13",
        "sh", "-c", "/sandbox/solution < /sandbox/input.txt"
    ], capture_output=True, text=True, timeout=5)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    print(f"Time: {elapsed_ms}ms")
    print(f"Return code:", run_result.returncode)
    print(f"Stdout: {run_result.stdout!r}")

    if run_result.returncode == 137:
        print("VERDICT: MLE")
    elif run_result.returncode != 0:
        print("VERDICT: RE")
    elif run_result.stdout.strip() != "7":
        print(f"VERDICT: WA (got {run_result.stdout.strip()!r}, expected '7')")
    else:
        print("VERDICT: AC")

except subprocess.TimeoutExpired:
    print("VERDICT: TLE")
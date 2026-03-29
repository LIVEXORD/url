import sys
import subprocess
import importlib.util
from cryptography.fernet import Fernet
import base64
import random
import time

time.sleep(random.uniform(0.3, 1.2))

REQUIRED_PACKAGES = {
    "requests": "requests",
    "cryptography": "cryptography",
    "colorama": "colorama",
}


def ensure_package(import_name, pip_name=None):
    if pip_name is None:
        pip_name = import_name

    if importlib.util.find_spec(import_name) is None:
        print(f"[BOOT] Installing dependency: {pip_name}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--quiet", pip_name]
        )


for mod, pkg in REQUIRED_PACKAGES.items():
    ensure_package(mod, pkg)

import requests  # noqa: E402
import hashlib  # noqa: E402
import uuid  # noqa: E402
import platform  # noqa: E402
import socket  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import time  # noqa: E402
import os  # noqa: E402
from datetime import datetime  # noqa: E402
from colorama import Fore, init  # noqa: E402

init(autoreset=True)

VERIFY_SERVER = None
PING_SERVER = None
RAW_REPO_URL = "https://raw.githubusercontent.com/LIVEXORD/url/refs/heads/main/url.txt"
CONFIG_FILE = "config.json"
_KEY_PARTS = [
    "TozbaVD6cr1Bg_",
    "JJqxlLEF8bmPXo",
    "S7rRXAEZTR_Sl5g="
]
KEY = "".join(_KEY_PARTS).encode()
SESSION = None


def now_ts():
    return datetime.now().strftime("[%Y:%m:%d ~ %H:%M:%S] |")


def log(message, color=Fore.RESET):
    safe_message = str(message).encode("utf-8", "backslashreplace").decode("utf-8")
    print(Fore.LIGHTBLACK_EX + now_ts() + " " + color + safe_message + Fore.RESET)


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except:
        log("❌ config.json not found / invalid", Fore.RED)
        sys.exit(1)


def fetch_server_url(max_retry=5):
    delay = 1.5
    for attempt in range(1, max_retry + 1):
        try:
            r = requests.get(RAW_REPO_URL, timeout=10)
            r.raise_for_status()

            url = r.text.strip().rstrip("/")
            if not url.startswith("http"):
                raise Exception("invalid url content")

            return url

        except Exception as e:
            if attempt >= max_retry:
                break
            log(f"⚠️ Fetch URL failed, retrying... ({attempt}/{max_retry}) [{e}]", Fore.YELLOW)
            time.sleep(delay)
            delay = min(delay * 1.6, 8)

    log("❌ Failed fetch server URL after retries", Fore.RED)
    sys.exit(1)


def strip_all():
    import gc  # noqa: E402

    KEEP = {"__name__", "__builtins__", "__SESSION__", "os"}

    for k in list(globals().keys()):
        if k not in KEEP:
            globals()[k] = None

    for m in list(sys.modules.keys()):
        if not m.startswith(("builtins", "__main__")):
            sys.modules.pop(m, None)

    gc.collect()


def calc_hwid():
    raw = "|".join([str(uuid.getnode()), platform.system(), platform.machine(), socket.gethostname()])
    return hashlib.sha256(raw.encode()).hexdigest()


def get_fingerprint():
    return (calc_hwid(), platform.system())


def verify_license(key, config, max_retry=15):
    hwid, os_name = get_fingerprint()
    payload = {"key": key, "hwid": hwid, "os": os_name, "bot": config.get("bot"), "platform": "python"}
    delay = 1.0
    for attempt in range(1, max_retry + 1):
        try:
            r = requests.post(VERIFY_SERVER, json=payload, timeout=10)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                sleep_time = delay + random.uniform(0, 0.7)
                log(f"⚠️ Rate limited (429), retry in {sleep_time:.2f}s [attempt {attempt}]", Fore.YELLOW)
                time.sleep(sleep_time)
                delay = min(delay * 1.8, 20)
                continue
            log(f"❌ License rejected ({r.status_code}): {r.text}", Fore.RED)
            return None
        except Exception as e:
            log(f"⚠️ Verify error, retrying... ({e})", Fore.YELLOW)
            sleep_time = delay + random.uniform(0, 0.5)
            time.sleep(sleep_time)
            delay = min(delay * 1.6, 15)
    log("❌ Too many retries, verify still failing", Fore.RED)
    return None


def minimal_exec(blob_b64, key, session):
    import zlib  # noqa: E402

    if not isinstance(blob_b64, str) or len(blob_b64) < 100:
        sys.exit(1)
    inner_blob = Fernet(key).decrypt(blob_b64.encode())
    inner_blob = base64.b64decode(inner_blob)
    decrypted = Fernet(KEY).decrypt(inner_blob)
    src = zlib.decompress(decrypted).decode()

    if "__uid__" not in src:
        print("tampered blob detected")
        sys.exit(1)

    exec(compile(src, "<blob>", "exec"), {"__name__": "__main__", "__SESSION__": session})


def main():
    if sys.gettrace():
        sys.exit(1)
    global VERIFY_SERVER, PING_SERVER

    log("🎛️ LIVEXORDS Launcher initializing...", Fore.MAGENTA)
    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Fore.LIGHTBLACK_EX)

    config = load_config()

    log("🌐 Fetching server URL...", Fore.CYAN)
    url = fetch_server_url().rstrip("/")

    VERIFY_SERVER = f"{url}/verify"
    PING_SERVER = f"{url}/ping"

    key = config.get("license", {}).get("key")
    if not key:
        log("❌ License key not found in config.json", Fore.RED)
        sys.exit(1)

    log("🔐 Verifying license...", Fore.YELLOW)
    data = verify_license(key, config)
    if not data:
        sys.exit(1)

    if hashlib.sha256(data["blob"].encode()).hexdigest() != data["blob_hash"]:
        log("❌ Blob integrity check failed", Fore.RED)
        sys.exit(1)

    DEFAULT_UA = f"Python/{platform.python_version()} ({platform.system()})"

    data["session"]["server"] = {"ping": PING_SERVER, "verify": VERIFY_SERVER}
    data["session"]["ua"] = DEFAULT_UA

    log("✅ License verified!", Fore.GREEN)
    log("🚀 Loading tool...\n", Fore.MAGENTA)

    ek = data["ek"]
    if isinstance(ek, str):
        ek = base64.b64decode(ek)

    real_key = Fernet(KEY).decrypt(ek)
    derived_key = hashlib.sha256(real_key).digest()
    data["session"]["_k"] = base64.b64encode(derived_key).decode()

    minimal_exec(blob_b64=data["blob"], key=real_key, session=data["session"])

    strip_all()
    os._exit(0)


if __name__ == "__main__":
    main()

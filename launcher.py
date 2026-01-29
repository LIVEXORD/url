import sys
import subprocess
import importlib.util

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
KEY = b"TozbaVD6cr1Bg_JJqxlLEF8bmPXoS7rRXAEZTR_Sl5g="
SESSION = None
STOP = False


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
    import sys
    import gc

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


def heartbeat_loop():
    global STOP, SESSION
    fail = 0
    last_ok = time.time()
    while not STOP:
        time.sleep(120)
        try:
            if not SESSION:
                continue
            sid = SESSION.get("sid")
            r = requests.post(PING_SERVER, json={"sid": sid}, timeout=10)
            if r.status_code != 200:
                raise Exception("bad status")
            data = r.json()
            if not data.get("vip"):
                log("❌ License revoked by server", Fore.RED)
                os._exit(1)
            fail = 0
            last_ok = time.time()
            if "exp" in data:
                SESSION["exp"] = data["exp"]
        except Exception as e:
            fail += 1
            log(f"⚠️ Launcher heartbeat failed: {e}", Fore.YELLOW)
            if fail >= 5 and time.time() - last_ok > 600:
                log("❌ Launcher lost server too long", Fore.RED)
                os._exit(1)


def minimal_exec(blob_b64, key, session):
    import base64, zlib  # noqa: E401
    from cryptography.fernet import Fernet  # noqa: E402

    src = zlib.decompress(Fernet(key).decrypt(base64.b64decode(blob_b64)))

    exec(src, {"__name__": "__main__", "__SESSION__": session})


def main():
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

    data["session"]["server"] = {"ping": PING_SERVER, "verify": VERIFY_SERVER}

    log("✅ License verified!", Fore.GREEN)
    log("🚀 Loading tool...\n", Fore.MAGENTA)

    minimal_exec(blob_b64=data["blob"], key=KEY, session=data["session"])

    strip_all()
    os._exit(0)


if __name__ == "__main__":
    main()

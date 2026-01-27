import requests
import hashlib
import uuid
import platform
import socket
import json
import sys
import base64
import zlib
import random
import time
from cryptography.fernet import Fernet
import os
from datetime import datetime
from colorama import Fore, init

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


def fetch_server_url():
    try:
        r = requests.get(RAW_REPO_URL, timeout=5)
        url = r.text.strip().rstrip("/")
        if not url.startswith("http"):
            raise Exception("invalid url")
        return url
    except Exception as e:
        log(f"❌ Failed fetch server URL from repo: {e}", Fore.RED)
        sys.exit(1)


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


def run_blob(blob_b64: str, session: dict):
    encrypted = base64.b64decode(blob_b64)
    compressed = Fernet(KEY).decrypt(encrypted)
    source = zlib.decompress(compressed)
    exec(source, {"__name__": "__main__", "__SESSION__": session})


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

    run_blob(blob_b64=data["blob"], session=data["session"])


if __name__ == "__main__":
    main()

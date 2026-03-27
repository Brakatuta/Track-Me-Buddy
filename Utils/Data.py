import json
import os

# ── DPAPI-backed encryption ────────────────────────────────────────────────────
# On Windows, CryptProtectData / CryptUnprotectData bind the ciphertext to the
# current Windows user account.  No key is stored anywhere — the OS is the key.
# If pywin32 is not available the module falls back to plain JSON (no encryption).

try:
    import win32crypt
    _DPAPI_AVAILABLE = True
except ImportError:
    _DPAPI_AVAILABLE = False
    print("DATA: Module win32crypt is not available!")

def _dpapi_encrypt(plaintext_bytes: bytes) -> bytes:
    """Encrypt bytes with Windows DPAPI (current-user scope)."""
    encrypted = win32crypt.CryptProtectData(
        plaintext_bytes,
        "TrackMeBuddy",   
        None,             
        None,
        None,
        0,
    )
    return encrypted

def _dpapi_decrypt(ciphertext_bytes: bytes) -> bytes:
    """Decrypt bytes previously encrypted with Windows DPAPI."""
    _, plaintext = win32crypt.CryptUnprotectData(
        ciphertext_bytes,
        None,
        None,
        None,
        0,
    )
    return plaintext


# ── Public API ─────────────────────────────────────────────────────────────────

def save_data(file_path: str, content: dict, key=None) -> None:
    """
    Serialise content to JSON and write to file_path.

    Pass any truthy value for key to request DPAPI encryption.
    The extension is automatically changed to .lock for encrypted files.
    Falls back to plain JSON if pywin32 is not installed.
    """
    json_bytes = json.dumps(content, indent=4).encode("utf-8")

    if key:
        if _DPAPI_AVAILABLE:
            data_to_write = _dpapi_encrypt(json_bytes)
            # Endung sicher auf .lock ändern
            base, _ = os.path.splitext(file_path)
            file_path = base + ".lock"
        else:
            print("[Data] WARNING: pywin32 not installed — saving as plain JSON.")
            data_to_write = json_bytes
    else:
        data_to_write = json_bytes

    with open(file_path, "wb") as f:
        f.write(data_to_write)

def load_data(file_path: str, key=None) -> dict | None:
    """
    Load and deserialise JSON from file_path.

    Pass any truthy value for key to request DPAPI decryption.
    Returns None if the file does not exist.
    """
    if key:
        base, _ = os.path.splitext(file_path)
        potential_path = base + ".lock"
        if os.path.exists(potential_path):
            file_path = potential_path
        elif not os.path.exists(file_path):
            return None

    if not os.path.exists(file_path):
        return None

    with open(file_path, "rb") as f:
        raw = f.read()

    if key and _DPAPI_AVAILABLE:
        try:
            raw = _dpapi_decrypt(raw)
        except Exception as e:
            print(f"[Data] Decryption failed: {e}")
            return None

    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None
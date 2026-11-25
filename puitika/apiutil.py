"""Helper bersama untuk semua endpoint: ApiError dan pembacaan parameter dengan validasi."""
from flask import request

MAX_Q = 100


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def int_arg(name, default, lo, hi=None, clamp=False):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        v = int(raw)
    except ValueError:
        raise ApiError(400, f"Parameter '{name}' harus bilangan bulat.")
    if v < lo:
        raise ApiError(400, f"Parameter '{name}' minimal {lo}.")
    if hi is not None and v > hi:
        if clamp:
            return hi
        raise ApiError(400, f"Parameter '{name}' maksimal {hi}.")
    return v


def choice_arg(name, valid):
    v = request.args.get(name)
    if v is None or v == "":
        return None
    if v not in valid:
        raise ApiError(400, f"Parameter '{name}' tidak valid. Pilihan: {', '.join(valid)}.")
    return v


def q_arg():
    q = (request.args.get("q") or "").strip()
    if len(q) > MAX_Q:
        raise ApiError(400, f"Parameter 'q' maksimal {MAX_Q} karakter.")
    return q or None


def json_text(field, max_len, label="Teks"):
    """Ambil string tak kosong dari body JSON. ApiError 400 bila bentuknya salah, kosong, atau terlalu panjang."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get(field), str):
        raise ApiError(400, f'Kirim JSON berbentuk {{"{field}": "..."}}.')
    text = payload[field].strip()
    if not text:
        raise ApiError(400, f"{label} kosong.")
    if len(text) > max_len:
        raise ApiError(400, f"{label} terlalu panjang (maksimal {max_len} karakter).")
    return text, payload

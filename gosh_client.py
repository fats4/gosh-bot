"""Gosh Live API client for chat monitoring and replies."""

from __future__ import annotations

import hashlib
import hmac
import json
import platform as py_platform
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

ACCOUNT_TYPE_EMAIL = 9
ACCOUNT_TYPE_DEVICE = 1
TIM_SDK_APP_ID = 20011275
SIGNIN_TYPE_USER = "2"

LOGIN_ERROR_MESSAGES = {
    1035: (
        "Email/password ditolak. Pastikan kredensial benar dan sm_box_id masih valid "
        "(ambil ulang dari browser jika perlu)."
    ),
    1051: (
        "Login ditolak (token perangkat tidak valid). "
        "Coba isi sm_box_id di config.json atau jalankan: python3 get_sm_box_id.py"
    ),
}


class GoshClient:
    API_BASE = "https://api.gosh.com"
    APP_VERSION = "3.9.2"
    WEB_SECRET = "7QmC2ZL9A8xKfR4P"
    PC_SECRET = "A7fQ9K2mX8Zp4R3L"
    TIM_SEND_SCRIPT = Path(__file__).with_name("tim_send.js")

    DEFAULT_QUERY = {
        "app": "kick",
        "bid": "26",
        "ch": "website",
        "ctry": "id",
        "lang": "en",
        "os": "MacOS" if "Darwin" in py_platform.system() else "Linux",
        "pf": "pc",
        "us": "0",
        "vsn": APP_VERSION,
    }

    def __init__(
        self,
        cookies_file: str | None = None,
        *,
        load_cookies: bool = True,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Origin": "https://gosh.com",
                "Referer": "https://gosh.com/",
            }
        )
        self.device_id = uuid.uuid4().hex
        self.smid = self._generate_smid()
        self.uid: str | None = None
        self.sid: str | None = None
        self.tim_user_sig: str | None = None
        self.can_chat: bool | None = None
        self.user_profile: dict[str, Any] | None = None

        if load_cookies and cookies_file and Path(cookies_file).exists():
            self.load_cookies(cookies_file)

    @staticmethod
    def _generate_smid() -> str:
        return f"{time.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:32]}"

    @staticmethod
    def _md5_hex(value: str) -> str:
        return hashlib.md5(value.encode("utf-8")).hexdigest()

    def _sign(self, params: dict[str, str], platform: str = "pc") -> str:
        secret = self.WEB_SECRET if platform == "web" else self.PC_SECRET
        payload = "&".join(f"{key}={params[key]}" for key in sorted(params))
        return hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _build_signature(
        self,
        path: str,
        method: str,
        body: str | None,
        ts: str,
        platform: str = "pc",
    ) -> str:
        params = {
            "did": self.device_id,
            "method": method.upper(),
            "path": path.split("?")[0],
            "ts": ts,
            "uid": self.uid or "0",
        }
        if method.upper() == "POST":
            params["body"] = self._md5_hex(body or "")
            return self._sign(params, platform)
        return self._sign(params, platform)

    def _query(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params = {
            **self.DEFAULT_QUERY,
            "did": self.device_id,
            "smid": self.smid,
            "ts": str(int(time.time())),
            "uid": self.uid or "0",
        }
        if self.sid:
            params["sid"] = self.sid
        if extra:
            params.update(extra)
        return params

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        extra_query: dict[str, Any] | None = None,
        platform: str = "pc",
    ) -> requests.Response:
        api_path = path if path.startswith("/") else f"/{path}"
        query = self._query(extra_query)
        ts = query["ts"]
        body = json.dumps(json_body or {}, separators=(",", ":")) if method.upper() == "POST" else None
        signature = self._build_signature(api_path, method, body, ts, platform)
        url = f"{self.API_BASE}{api_path}?{urlencode(query)}"
        headers = {"X-Signature": signature}
        if method.upper() == "POST":
            return self.session.post(url, data=body, headers=headers, timeout=30)
        return self.session.get(url, headers=headers, timeout=30)

    def _set_cookie(self, name: str, value: str) -> None:
        self.session.cookies.set(name, str(value), domain=".gosh.com", path="/")

    def _apply_session(self, data: dict[str, Any]) -> None:
        """Mirror browser session setup after login."""
        user = data.get("user") or {}
        self.uid = str(user.get("id") or self.session.cookies.get("uid") or "")
        if not self.uid:
            raise RuntimeError("Login berhasil tapi uid tidak ditemukan.")

        login_did = user.get("login_did")
        if login_did:
            self.device_id = str(login_did)

        if data.get("smid"):
            self.smid = str(data["smid"])
        if data.get("sid"):
            self.sid = str(data["sid"])

        self.tim_user_sig = (
            data.get("tim_user_sig")
            or self.session.cookies.get("tim_user_sig")
        )
        self.can_chat = bool(user.get("can_chat") or user.get("is_can_chat"))

        self._set_cookie("uid", self.uid)
        self._set_cookie("signin_type", SIGNIN_TYPE_USER)
        self._set_cookie("user_type", str(user.get("user_type", 2)))
        self._set_cookie("ctry", str(user.get("country") or "id"))
        self._set_cookie("uid_created_at", str(user.get("created_at") or ""))
        self._set_cookie("did", self.device_id)
        self._set_cookie("smidV2", self.smid)
        if self.tim_user_sig:
            self._set_cookie("tim_user_sig", self.tim_user_sig)

        try:
            self._request("POST", "/gosh_3rdimlive/app/sys/device", json_body={})
        except requests.RequestException:
            pass

    def load_cookies(self, cookies_file: str) -> None:
        raw = json.loads(Path(cookies_file).read_text(encoding="utf-8"))
        session = raw.get("session") if isinstance(raw, dict) else None
        if isinstance(session, dict):
            self.sid = session.get("sid") or self.sid
            self.tim_user_sig = session.get("tim_user_sig") or self.tim_user_sig
            self.can_chat = session.get("can_chat", self.can_chat)
            if session.get("smid"):
                self.smid = str(session["smid"])
            if session.get("did"):
                self.device_id = str(session["did"])

        cookies = raw if isinstance(raw, list) else raw.get("cookies", [])
        for cookie in cookies:
            self.session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ".gosh.com"),
                path=cookie.get("path", "/"),
            )
        for name in ("uid", "did", "smidV2", "tim_user_sig"):
            value = self.session.cookies.get(name)
            if name == "uid" and value:
                self.uid = value
            elif name == "did" and value:
                self.device_id = value
            elif name == "smidV2" and value:
                self.smid = value
            elif name == "tim_user_sig" and value:
                self.tim_user_sig = value

    def save_cookies(self, cookies_file: str) -> None:
        cookies = [
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
            }
            for c in self.session.cookies
        ]
        payload = {
            "cookies": cookies,
            "session": {
                "uid": self.uid,
                "did": self.device_id,
                "smid": self.smid,
                "sid": self.sid,
                "tim_user_sig": self.tim_user_sig,
                "can_chat": self.can_chat,
            },
        }
        Path(cookies_file).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def login(
        self,
        email: str,
        password: str,
        sm_box_id: str | None = None,
    ) -> dict[str, Any]:
        if not sm_box_id:
            raise RuntimeError(
                "sm_box_id wajib untuk login email. "
                "Isi di config.json atau jalankan: python3 get_sm_box_id.py"
            )

        response = self._request(
            "POST",
            "/gosh_base/app/user/login",
            json_body={
                "account_type": ACCOUNT_TYPE_EMAIL,
                "account_id": email,
                "password": password,
                "sm_box_id": sm_box_id,
                "is_use_password": True,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            code = payload.get("code")
            hint = LOGIN_ERROR_MESSAGES.get(code, "")
            detail = payload.get("toast") or payload.get("message") or payload
            raise RuntimeError(
                f"Login gagal (code {code}): {detail}.{f' {hint}' if hint else ''}"
            )

        self._apply_session(payload.get("data") or {})
        self.refresh_user_profile()
        return payload

    def refresh_user_profile(self) -> dict[str, Any]:
        response = self._request(
            "GET",
            "/gosh_base/app/user/user_info",
            extra_query={"user_id": self.uid or "0"},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"user_info gagal: {payload}")
        user = payload.get("data", {}).get("user") or {}
        self.user_profile = self._chat_user_payload(user)
        return self.user_profile

    @staticmethod
    def _chat_user_payload(user: dict[str, Any]) -> dict[str, Any]:
        """Bentuk objek user seperti payload chat Gosh (TIM custom message)."""
        allowed = (
            "id",
            "show_id",
            "user_type",
            "nickname",
            "avatar",
            "sex",
            "bio",
            "country",
            "show_country",
            "birthday",
            "created_at",
            "updated_at",
            "del_at",
            "login_did",
            "lang",
            "lang_follow",
            "user_level",
            "active_level",
            "is_can_chat",
            "last_online_at",
            "bot_type",
            "app",
            "smid",
            "channel",
            "bind_withdraw",
            "register_ip",
            "login_platform",
            "is_recharge",
            "app_id",
            "channel_id",
            "agent_id",
            "is_koc",
            "source_channel",
            "has_password",
            "is_inspector",
            "noble_status",
            "live_mystery",
            "rank_mystery",
            "chat_mystery",
            "identity_info",
            "is_agency_owner",
            "is_agency_bd",
            "is_channel_owner",
            "name_color",
        )
        out: dict[str, Any] = {}
        for key in allowed:
            if key in user and user[key] is not None:
                out[key] = user[key]
        out["password"] = ""
        return out

    def fetch_messages(self, anchor_id: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/gosh_3rdimlive/app/group_chat/fetch_msg",
            json_body={"anchor_id": int(anchor_id)},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"fetch_msg gagal: {payload}")
        return payload.get("data") or {}

    def get_commenter_room(self, user_id: str) -> dict[str, Any] | None:
        """Ambil room/profil Gosh user (online atau offline)."""
        response = self._request(
            "GET",
            "/gosh_base/app/live/get_by_anchor_v1",
            extra_query={"anchor_id": user_id},
        )
        if response.status_code == 401:
            return None
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            return None
        data = payload.get("data")
        if isinstance(data, dict) and "live" in data:
            return data["live"]
        return data if isinstance(data, dict) else None

    @staticmethod
    def resolve_chat_target(
        room: dict[str, Any] | None,
        user_id: str,
    ) -> tuple[str, str] | None:
        """Ambil (group_id, live_id) untuk chat penonton."""
        if not room:
            return None

        live_id = str(room.get("id") or room.get("live_id") or "")
        if not live_id or live_id == "0":
            return None

        for key in ("im_room", "avc_room"):
            value = room.get(key)
            if value:
                return str(value), live_id

        return f"@AVC#{user_id}", live_id

    def get_live_by_anchor(
        self,
        anchor_id: str,
        *,
        raise_on_auth_error: bool = False,
    ) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            "/gosh_base/app/live/get_by_anchor_v1",
            extra_query={"anchor_id": anchor_id},
        )
        if response.status_code == 401:
            if raise_on_auth_error:
                raise RuntimeError("Sesi login expired. Login ulang atau perbarui cookies.")
            return None
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            return None
        live = payload.get("data")
        if isinstance(live, dict) and "live" in live:
            live = live["live"]
        if not live:
            return None
        return live

    def _send_via_tim(
        self,
        group_id: str,
        live_id: str,
        text: str,
    ) -> dict[str, Any]:
        if not self.tim_user_sig or not self.uid:
            raise RuntimeError("tim_user_sig tidak ada. Login ulang.")
        if not self.user_profile:
            self.refresh_user_profile()
        if not self.TIM_SEND_SCRIPT.exists():
            raise RuntimeError(
                f"Script TIM tidak ditemukan: {self.TIM_SEND_SCRIPT}. "
                "Jalankan: cd gosh-bot && npm install"
            )

        payload = {
            "sdkappid": TIM_SDK_APP_ID,
            "userid": self.uid,
            "usersig": self.tim_user_sig,
            "group_id": group_id,
            "live_id": live_id,
            "text": text,
            "user": self.user_profile,
        }
        try:
            proc = subprocess.run(
                ["node", str(self.TIM_SEND_SCRIPT)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Node.js tidak ditemukan. Install Node.js lalu jalankan: npm install"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Kirim chat timeout (TIM SDK).") from exc

        output = (proc.stdout or "").strip()
        if proc.returncode != 0:
            err = (proc.stderr or output or "").strip()
            if "invalid group id" in err.lower():
                raise RuntimeError(
                    "Penonton sedang offline / tidak punya live room aktif."
                )
            raise RuntimeError(err or "Gagal kirim chat via TIM SDK.")

        for line in reversed(output.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    match = re.search(r'\{.*\}', line)
                    if match:
                        try:
                            return json.loads(match.group(0))
                        except json.JSONDecodeError:
                            continue
        match = re.search(r'\{"ok"\s*:\s*true[^}]*\}', output)
        if match:
            return json.loads(match.group(0))
        raise RuntimeError("Respons TIM SDK tidak valid.")

    def send_chat_message(
        self,
        anchor_id: str,
        live_id: str,
        text: str,
        *,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        del anchor_id
        if not group_id:
            raise RuntimeError("Group chat penonton tidak ditemukan.")
        if not live_id:
            raise RuntimeError("Live ID penonton tidak ditemukan.")
        return self._send_via_tim(group_id, live_id, text)

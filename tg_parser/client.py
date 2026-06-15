import asyncio
import getpass
import io
import json
import pathlib

import qrcode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import SQLiteSession

SESSION_DIR = pathlib.Path("session")
CONFIG_FILE = SESSION_DIR / "config.json"


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def _save_config(data: dict) -> None:
    SESSION_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def _ask_credentials() -> tuple[str, str]:
    print("\nДля работы нужны API_ID и API_HASH.")
    print("Получите их на https://my.telegram.org/apps\n")
    api_id = input("API_ID: ").strip()
    api_hash = input("API_HASH: ").strip()
    return api_id, api_hash


def build_client() -> TelegramClient:
    SESSION_DIR.mkdir(exist_ok=True)

    config = _load_config()
    api_id = config.get("api_id")
    api_hash = config.get("api_hash")

    if not api_id or not api_hash:
        api_id, api_hash = _ask_credentials()
        _save_config({"api_id": api_id, "api_hash": api_hash})
        print("Данные сохранены.\n")

    return TelegramClient(
        SQLiteSession(str(SESSION_DIR / "user")),
        api_id=int(api_id),
        api_hash=api_hash,
    )


def _print_qr(url: str) -> None:
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)

    f = io.StringIO()
    qr.print_ascii(out=f, invert=True)
    print(f.getvalue())


async def connect_qr(client: TelegramClient) -> None:
    await client.connect()

    while True:
        qr_login = await client.qr_login()
        print("\nОткройте Telegram → Настройки → Устройства → Подключить устройство\nи отсканируйте QR-код:\n")
        _print_qr(qr_login.url)

        try:
            await qr_login.wait(30)
            break
        except asyncio.TimeoutError:
            print("QR-код истёк, генерирую новый...\n")
            continue
        except SessionPasswordNeededError:
            password = getpass.getpass("Введите пароль двухфакторной аутентификации: ")
            await client.sign_in(password=password)
            break


async def connect_phone(client: TelegramClient) -> None:
    phone = input("Номер телефона (например +79001234567): ").strip()

    async def password_cb():
        return getpass.getpass("Пароль двухфакторной аутентификации: ")

    await client.start(phone=phone, password=password_cb)

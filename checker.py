import re
import time
from pathlib import Path

import psutil
import win32con
import win32gui
from pywinauto import Desktop


# =========
# НАСТРОЙКИ
# =========

INPUT_FILE = "usernames.txt"

# Максимум ожидания ответа от Telegram (сек)
RESULT_TIMEOUT = 0.30

# Как часто опрашивать статус в окне (сек)
POLL_INTERVAL = 0.19

# Небольшая задержка перед чтением ответа (сек)
MIN_RESULT_DELAY = 0.19

# Максимум ожидания исчезновения старого ответа (сек)
CLEAR_STATUS_TIMEOUT = 0.22

# Пауза после очистки поля (сек)
AFTER_CLEAR_DELAY = 0.15

# Пауза между юзернеймами (сек, 0 = без паузы)
BETWEEN_USERNAMES = 0.15

# Повторные проверки при статусе UNKNOWN (0 = без повторов)
RETRIES = 0


# ================
# СТАТУСЫ TELEGRAM
# ================

FREE_PATTERNS = (
    "это имя пользователя доступно",
    "is available",
)

TAKEN_PATTERNS = (
    "это имя пользователя уже занято",
    "is already taken",
    "already taken",
)

INVALID_PATTERNS = (
    "некорректное имя пользователя",
    "это имя пользователя некорректно",
    "недопустимое имя пользователя",
    "слишком короткое",
    "invalid username",
    "username is invalid",
    "this username is invalid",
    "must have at least 5 characters",
    "can't use this username",
)

FRAGMENT_PATTERNS = (
    "выставлена на продажу",
    "вы можете ее купить",
    "available on fragment",
    "put up for auction",
    "buy it on fragment",
)

RATE_LIMIT_PATTERNS = (
    "слишком много попыток",
    "попробуйте позже",
    "too many attempts",
    "please try again later",
)

ICONS = {
    "FREE": "✅",
    "TAKEN": "❌",
    "FRAGMENT": "💎",
    "INVALID": "⚠️",
    "RATE_LIMIT": "⏳",
    "UNKNOWN": "❓",
}

USERNAME_RE = re.compile(r"^[A-Za-z](?!.*__)[A-Za-z0-9_]{3,30}[A-Za-z0-9]$")
TME_PREFIX_RE = re.compile(r"^https?://(?:www\.)?t\.me/", flags=re.IGNORECASE)


# ==================
# РАБОТА С ФАЙЛАМИ
# ==================

def get_output_file() -> Path:
    first = Path("free.txt")
    if not first.exists():
        return first

    index = 1
    while True:
        candidate = Path(f"free{index}.txt")
        if not candidate.exists():
            return candidate
        index += 1


def save_free(output_file: Path, username: str) -> None:
    """Записывает свободный юзернейм в выходной файл."""
    with output_file.open("a", encoding="utf-8") as f:
        f.write(f"{username}\n")
        f.flush()


# ==================
# РАБОТА С USERNAMES
# ==================

def normalize_username(value: str) -> str:
    value = value.strip()
    value = TME_PREFIX_RE.sub("", value)
    value = value.lstrip("@")
    value = value.split("?")[0]
    value = value.split("/")[0]
    return value.strip()


def is_valid_username(username: str) -> bool:
    """
    Локальная проверка по правилам Telegram:
    - длина от 5 до 32 символов;
    - только латинские буквы, цифры и _;
    - начинается с буквы, заканчивается буквой или цифрой;
    - без двух _ подряд.
    """
    if not 5 <= len(username) <= 32:
        return False
    return bool(USERNAME_RE.fullmatch(username))


def load_usernames() -> tuple[list[str], list[str]]:
    path = Path(INPUT_FILE)
    if not path.exists():
        raise FileNotFoundError(f"не найден файл {INPUT_FILE}")

    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        username = normalize_username(line)
        if not username:
            continue

        key = username.lower()
        if key in seen:
            continue
        seen.add(key)

        if is_valid_username(username):
            valid.append(username)
        else:
            invalid.append(username)

    return valid, invalid


# =====================
# ПОИСК ОКНА И ПОЛЯ UI
# =====================

def find_telegram_window():
    pids = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name == "telegram.exe":
                pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not pids:
        raise RuntimeError("Telegram.exe не найден (запустите Telegram Desktop)")

    desktop = Desktop(backend="uia")
    windows = []

    for pid in pids:
        try:
            windows.extend(desktop.windows(process=pid, visible_only=False))
        except Exception:
            pass

    if not windows:
        raise RuntimeError("Окно Telegram не найдено")

    def get_area(win) -> int:
        try:
            rect = win.rectangle()
            return rect.width() * rect.height()
        except Exception:
            return 0

    return max(windows, key=get_area)


def find_username_field(window):
    for control in window.descendants():
        try:
            info = control.element_info
            control_type = str(getattr(info, "control_type", ""))
            class_name = str(getattr(info, "class_name", ""))
            name = str(getattr(info, "name", ""))

            if (
                control_type == "Edit"
                and class_name == "class Ui::UsernameInput"
                and name == "@username"
            ):
                return control
        except Exception:
            pass

    raise RuntimeError(
        "поле @username не найдено (откройте окно выбора имени пользователя в Telegram)"
    )


# ===========================
# ОПРЕДЕЛЕНИЕ СТАТУСА В ОКНЕ
# ===========================

def normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


def get_status_fast(window) -> str | None:
    """Читает text-контролы окна Telegram и возвращает статус."""
    try:
        controls = window.descendants(control_type="Text")
    except Exception:
        return None

    for control in controls:
        try:
            raw_text = control.element_info.name or ""
            text = normalize_text(raw_text)
            if not text:
                continue

            # FRAGMENT проверяем первым, т.к. в тексте тоже есть слово "занята"
            for pattern in FRAGMENT_PATTERNS:
                if pattern in text:
                    return "FRAGMENT"

            for pattern in RATE_LIMIT_PATTERNS:
                if pattern in text:
                    return "RATE_LIMIT"

            for pattern in FREE_PATTERNS:
                if pattern in text:
                    return "FREE"

            for pattern in TAKEN_PATTERNS:
                if pattern in text:
                    return "TAKEN"

            for pattern in INVALID_PATTERNS:
                if pattern in text:
                    return "INVALID"

        except Exception:
            pass

    return None


# ================
# BACKGROUND INPUT
# ================

def post_key(hwnd: int, vk: int) -> None:
    """Отправляет нажатие клавиши напрямую в окно через Win32 API."""
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 1)
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0xC0000001)


def post_char(hwnd: int, char: str) -> None:
    """Отправляет символ напрямую в окно через Win32 API."""
    win32gui.PostMessage(hwnd, win32con.WM_CHAR, ord(char), 1)


def clear_username_field(hwnd: int) -> None:
    """Очищает поле ввода (максимальная длина username в Telegram — 32 символа)."""
    post_key(hwnd, win32con.VK_END)
    for _ in range(32):
        post_key(hwnd, win32con.VK_BACK)


def type_username(hwnd: int, username: str) -> None:
    """Посимвольно вводит юзернейм в поле."""
    for char in username:
        post_char(hwnd, char)


# ================
# ЛОГИКА ПРОВЕРКИ
# ================

def wait_old_status_disappears(window) -> bool:
    started = time.monotonic()
    while True:
        if get_status_fast(window) is None:
            return True
        if time.monotonic() - started >= CLEAR_STATUS_TIMEOUT:
            return False
        time.sleep(POLL_INTERVAL)


def check_username(window, hwnd: int, username: str) -> tuple[str, float]:
    for attempt in range(RETRIES + 1):
        # 1. Очищаем предыдущий username и ждём исчезновения старого статуса
        clear_username_field(hwnd)
        wait_old_status_disappears(window)

        if AFTER_CLEAR_DELAY > 0:
            time.sleep(AFTER_CLEAR_DELAY)

        # 2. Вводим новый username
        type_username(hwnd, username)
        started = time.monotonic()

        # 3. Ждём ответ от Telegram
        while True:
            elapsed = time.monotonic() - started

            if elapsed >= MIN_RESULT_DELAY:
                status = get_status_fast(window)
                if status:
                    return status, elapsed

            if elapsed >= RESULT_TIMEOUT:
                break

            time.sleep(POLL_INTERVAL)

        if attempt < RETRIES:
            time.sleep(0.15)

    return "UNKNOWN", RESULT_TIMEOUT


# ====
# MAIN
# ====

def main() -> None:
    print()
    print("Telegram Username Checker FAST")
    print("=" * 66)

    try:
        usernames, local_invalid = load_usernames()
    except Exception as error:
        print(f"❌ {error}")
        return

    try:
        window = find_telegram_window()
        username_field = find_username_field(window)
    except Exception as error:
        print(f"❌ {error}")
        return

    hwnd = window.handle
    output_file = get_output_file()
    output_file.touch(exist_ok=False)

    print(f"загружено:        {len(usernames)}")
    print(f"локально INVALID: {len(local_invalid)}")
    print(f"FREE-файл:        {output_file.name}")
    print()
    print("поле @username найдено.")
    print()

    try:
        username_field.set_focus()
    except Exception as error:
        print("❌ не удалось установить фокус на поле username:")
        print(repr(error))
        return

    time.sleep(0.3)
    print("проверка запущена.")
    print()

    stats = {
        "FREE": 0,
        "TAKEN": 0,
        "FRAGMENT": 0,
        "INVALID": len(local_invalid),
        "UNKNOWN": 0,
        "RATE_LIMIT": 0,
    }

    total = len(usernames)
    start_total = time.perf_counter()
    checked = 0

    try:
        for index, username in enumerate(usernames, start=1):
            status, elapsed = check_username(window, hwnd, username)
            checked += 1
            stats[status] += 1

            if status == "FREE":
                save_free(output_file, username)

            total_elapsed = time.perf_counter() - start_total
            speed = checked / total_elapsed if total_elapsed > 0 else 0
            icon = ICONS.get(status, "❓")

            print(
                f"[{index:>5}/{total}] "
                f"@{username:<32} "
                f"{icon} {status:<11} "
                f"{elapsed:.2f}s | {speed:.2f}/s",
                flush=True,
            )

            if BETWEEN_USERNAMES > 0 and index < total:
                time.sleep(BETWEEN_USERNAMES)

    except KeyboardInterrupt:
        print("\nпроверка остановлена пользователем.")

    # =======
    # SUMMARY
    # =======

    total_elapsed = time.perf_counter() - start_total

    print()
    print("=" * 66)
    print("ГОТОВО")
    print("=" * 66)
    print(f"✅ FREE:      {stats['FREE']}")
    print(f"❌ TAKEN:     {stats['TAKEN']}")
    print(f"💎 FRAGMENT:  {stats['FRAGMENT']}")
    print(f"⚠️ INVALID:   {stats['INVALID']}")
    print(f"❓ UNKNOWN:   {stats['UNKNOWN']}")

    if stats["RATE_LIMIT"] > 0:
        print(f"⏳ RATE LIMIT: {stats['RATE_LIMIT']}")

    print()
    print(f"проверено: {checked}")
    print(f"время: {total_elapsed:.2f} сек.")

    if total_elapsed > 0:
        print(f"скорость: {checked / total_elapsed:.2f} username/s")

    print()
    print("свободные usernames:")
    print(f"→ {output_file.name}")


if __name__ == "__main__":
    main()

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psutil
import win32con
import win32gui
from pywinauto import Desktop


VERSION = "1.0.0"

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent


# --- ANSI Colors ---

class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


def c(text: str, color: str) -> str:
    return f"{color}{text}{Style.RESET}"


# --- Configuration ---

@dataclass
class Config:
    input_file: str = "usernames.txt"
    result_timeout: float = 0.30
    poll_interval: float = 0.19
    min_result_delay: float = 0.19
    clear_status_timeout: float = 0.22
    after_clear_delay: float = 0.15
    between_usernames: float = 0.15
    retries: int = 0


CONFIG = Config()


# --- Telegram UI Patterns ---

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

STATUS_COLORS = {
    "FREE": Style.GREEN,
    "TAKEN": Style.RED,
    "FRAGMENT": Style.CYAN,
    "INVALID": Style.YELLOW,
    "RATE_LIMIT": Style.YELLOW,
    "UNKNOWN": Style.DIM,
}

USERNAME_RE = re.compile(r"^[A-Za-z](?!.*__)[A-Za-z0-9_]{3,30}[A-Za-z0-9]$")
TME_PREFIX_RE = re.compile(r"^https?://(?:www\.)?t\.me/", flags=re.IGNORECASE)


# --- Console Helpers ---

def init_console() -> None:
    os.system("")  # Enable VT100 ANSI escape sequences on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
        os.system(f"title tg-checker v{VERSION}")


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause(prompt: str = "\nНажмите Enter для возврата в меню...") -> None:
    try:
        input(c(prompt, Style.DIM))
    except (KeyboardInterrupt, EOFError):
        pass


def print_header(subtitle: str = "") -> None:
    line = c("─" * 68, Style.DIM)
    title = f" {c('tg-checker', Style.BOLD + Style.WHITE)} {c(f'v{VERSION}', Style.DIM)}"
    if subtitle:
        title += f" {c('::', Style.DIM)} {c(subtitle, Style.CYAN)}"
    print(line)
    print(title)
    print(line)


# --- File I/O ---

def get_input_path() -> Path:
    path = Path(CONFIG.input_file)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def ensure_input_file_exists() -> Path:
    path = get_input_path()
    if not path.exists():
        path.write_text(
            "# Список юзернеймов (по одному на строку)\n"
            "# Форматы: username, @username, https://t.me/username\n",
            encoding="utf-8",
        )
    return path


def get_output_file() -> Path:
    first = BASE_DIR / "free.txt"
    if not first.exists():
        return first

    index = 1
    while True:
        candidate = BASE_DIR / f"free{index}.txt"
        if not candidate.exists():
            return candidate
        index += 1


def get_latest_free_file() -> Path | None:
    files = sorted(
        BASE_DIR.glob("free*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def save_free(output_file: Path, username: str) -> None:
    with output_file.open("a", encoding="utf-8") as f:
        f.write(f"{username}\n")
        f.flush()


# --- Username Validation ---

def normalize_username(value: str) -> str:
    value = value.strip()
    if not value or value.startswith("#"):
        return ""
    value = TME_PREFIX_RE.sub("", value)
    value = value.lstrip("@")
    value = value.split("?")[0]
    value = value.split("/")[0]
    return value.strip()


def is_valid_username(username: str) -> bool:
    if not 5 <= len(username) <= 32:
        return False
    return bool(USERNAME_RE.fullmatch(username))


def load_usernames() -> tuple[list[str], list[str]]:
    path = ensure_input_file_exists()

    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
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


# --- Telegram Window & UIA ---

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
        raise RuntimeError("Процесс Telegram.exe не найден (запустите Telegram Desktop)")

    desktop = Desktop(backend="uia")
    windows = []

    for pid in pids:
        try:
            windows.extend(desktop.windows(process=pid, visible_only=False))
        except Exception:
            pass

    if not windows:
        raise RuntimeError("Окно Telegram Desktop не найдено")

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
        "Поле @username не найдено (откройте окно выбора имени пользователя в Telegram)"
    )


def get_telegram_status_summary() -> str:
    try:
        win = find_telegram_window()
    except Exception:
        return c("НЕ ЗАПУЩЕН", Style.RED) + c(" (Telegram.exe не найден)", Style.DIM)

    try:
        find_username_field(win)
        return c("ГОТОВ", Style.GREEN) + c(f" (HWND: {win.handle:#x}, поле @username найдено)", Style.DIM)
    except Exception:
        return c("ОЖИДАНИЕ ПОЛЯ", Style.YELLOW) + c(" (откройте окно изменения @username)", Style.DIM)


# --- Status Parsing ---

def normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


def get_status_fast(window) -> str | None:
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


# --- Win32 Background Input ---

def post_key(hwnd: int, vk: int) -> None:
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 1)
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0xC0000001)


def post_char(hwnd: int, char: str) -> None:
    win32gui.PostMessage(hwnd, win32con.WM_CHAR, ord(char), 1)


def clear_username_field(hwnd: int) -> None:
    post_key(hwnd, win32con.VK_END)
    for _ in range(32):
        post_key(hwnd, win32con.VK_BACK)


def type_username(hwnd: int, username: str) -> None:
    for char in username:
        post_char(hwnd, char)


# --- Core Check Loop ---

def wait_old_status_disappears(window) -> bool:
    started = time.monotonic()
    while True:
        if get_status_fast(window) is None:
            return True
        if time.monotonic() - started >= CONFIG.clear_status_timeout:
            return False
        time.sleep(CONFIG.poll_interval)


def check_username(window, hwnd: int, username: str) -> tuple[str, float]:
    for attempt in range(CONFIG.retries + 1):
        clear_username_field(hwnd)
        wait_old_status_disappears(window)

        if CONFIG.after_clear_delay > 0:
            time.sleep(CONFIG.after_clear_delay)

        type_username(hwnd, username)
        started = time.monotonic()

        while True:
            elapsed = time.monotonic() - started

            if elapsed >= CONFIG.min_result_delay:
                status = get_status_fast(window)
                if status:
                    return status, elapsed

            if elapsed >= CONFIG.result_timeout:
                break

            time.sleep(CONFIG.poll_interval)

        if attempt < CONFIG.retries:
            time.sleep(0.15)

    return "UNKNOWN", CONFIG.result_timeout


def run_checker() -> None:
    clear_screen()
    print_header("проверка списка")

    try:
        usernames, local_invalid = load_usernames()
    except Exception as error:
        print(f"\n {c('[ОШИБКА]', Style.RED)} {error}")
        pause()
        return

    if not usernames:
        print(f"\n {c('[ВНИМАНИЕ]', Style.YELLOW)} В файле {get_input_path().name} нет валидных записей.")
        if local_invalid:
            print(f" Отфильтровано невалидных: {len(local_invalid)}")
        print(" Добавьте юзернеймы через пункт [3] и запустите проверку снова.")
        pause()
        return

    try:
        window = find_telegram_window()
        username_field = find_username_field(window)
    except Exception as error:
        print(f"\n {c('[ОШИБКА]', Style.RED)} {error}")
        pause()
        return

    hwnd = window.handle
    output_file = get_output_file()
    output_file.touch(exist_ok=False)

    print(f" Входной файл   : {get_input_path().name} (валидных: {len(usernames)}, отсеяно: {len(local_invalid)})")
    print(f" Выходной файл  : {output_file.name}")
    print(f" Дескриптор     : {hwnd:#x} (Ui::UsernameInput)")
    print(c("─" * 68, Style.DIM))

    try:
        username_field.set_focus()
    except Exception as error:
        print(f"\n {c('[ОШИБКА]', Style.RED)} Не удалось установить фокус на поле @username: {error!r}")
        pause()
        return

    time.sleep(0.3)
    print(f" {c('Запущено. Нажмите Ctrl+C для остановки.', Style.DIM)}\n")

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

            color = STATUS_COLORS.get(status, Style.WHITE)
            status_tag = c(f"{status:<10}", color)
            idx_str = c(f"[{index:>5}/{total}]", Style.DIM)
            metrics = c(f"{elapsed:.2f}s | {speed:.2f}/s", Style.DIM)

            print(
                f" {idx_str}  @{username:<32}  {status_tag}  {metrics}",
                flush=True,
            )

            if CONFIG.between_usernames > 0 and index < total:
                time.sleep(CONFIG.between_usernames)

    except KeyboardInterrupt:
        print(f"\n {c('[ОСТАНОВЛЕНО ПОЛЬЗОВАТЕЛЕМ]', Style.YELLOW)}")

    total_elapsed = time.perf_counter() - start_total

    print()
    print(c("─" * 68, Style.DIM))
    print(f" {c('ИТОГИ ПРОВЕРКИ', Style.BOLD)}")
    print(c("─" * 68, Style.DIM))
    print(f"  FREE        : {c(str(stats['FREE']), Style.GREEN)}")
    print(f"  TAKEN       : {stats['TAKEN']}")
    print(f"  FRAGMENT    : {c(str(stats['FRAGMENT']), Style.CYAN)}")
    print(f"  INVALID     : {stats['INVALID']}")
    print(f"  UNKNOWN     : {stats['UNKNOWN']}")

    if stats["RATE_LIMIT"] > 0:
        print(f"  RATE_LIMIT  : {c(str(stats['RATE_LIMIT']), Style.YELLOW)}")

    print(c("─" * 68, Style.DIM))
    print(f"  Обработано  : {checked} из {total}")
    print(f"  Время       : {total_elapsed:.2f} сек")

    if total_elapsed > 0 and checked > 0:
        print(f"  Скорость    : {checked / total_elapsed:.2f} username/s")

    print(f"  Результат   : {c(output_file.name, Style.GREEN)}")
    print(c("─" * 68, Style.DIM))
    pause()


# --- Menu Screens ---

def check_connection_screen() -> None:
    clear_screen()
    print_header("диагностика окна Telegram")

    try:
        win = find_telegram_window()
        rect = win.rectangle()
        print(f"\n  Процесс Telegram.exe : {c('НАЙДЕН', Style.GREEN)}")
        print(f"  Дескриптор окна      : {win.handle:#x} ({rect.width()}x{rect.height()})")
    except Exception as e:
        print(f"\n  {c('[ОШИБКА]', Style.RED)} {e}")
        pause()
        return

    try:
        field = find_username_field(win)
        field.set_focus()
        current_status = get_status_fast(win)
        print(f"  Поле @username       : {c('ДОСТУПНО', Style.GREEN)} (Ui::UsernameInput)")
        print(f"  Текущий статус       : {current_status or 'нет (поле пустое)'}")
    except Exception as e:
        print(f"  Поле @username       : {c('НЕ НАЙДЕНО', Style.YELLOW)}")
        print(f"\n  {c('Детали:', Style.DIM)} {e}")
        print("  Откройте в Telegram Desktop: Настройки -> Мой аккаунт -> Имя пользователя")
        print("  (или настройки публичной ссылки канала/группы) и оставьте окно открытым.")

    pause()


def open_usernames_file() -> None:
    path = ensure_input_file_exists()
    try:
        subprocess.Popen(["notepad.exe", str(path)])
    except Exception as e:
        print(f"\n {c('[ОШИБКА]', Style.RED)} Не удалось запустить notepad.exe: {e}")
        pause()


def view_free_results() -> None:
    clear_screen()
    print_header("результаты (free)")

    latest = get_latest_free_file()
    if not latest:
        print("\n  Файлы free*.txt отсутствуют.")
        pause()
        return

    lines = [
        line.strip()
        for line in latest.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    ]

    print(f"\n  Файл: {c(latest.name, Style.WHITE)} (записей: {len(lines)})\n")
    if lines:
        for idx, name in enumerate(lines[:50], start=1):
            print(f"  {idx:>4}. @{name}")
        if len(lines) > 50:
            print(c(f"\n  ... ещё {len(lines) - 50} строк", Style.DIM))
    else:
        print(c("  (файл пуст)", Style.DIM))

    print("\n" + c("─" * 68, Style.DIM))
    choice = input("  Открыть файл в Блокноте? [y/N]: ").strip().lower()
    if choice in ("y", "д", "да", "yes"):
        try:
            subprocess.Popen(["notepad.exe", str(latest)])
        except Exception:
            pass


def settings_menu() -> None:
    while True:
        clear_screen()
        print_header("параметры")
        print(f"  [1] Входной файл (INPUT_FILE)            : {CONFIG.input_file}")
        print(f"  [2] Таймаут ответа (RESULT_TIMEOUT)      : {CONFIG.result_timeout:.2f} s")
        print(f"  [3] Интервал опроса (POLL_INTERVAL)      : {CONFIG.poll_interval:.2f} s")
        print(f"  [4] Задержка чтения (MIN_RESULT_DELAY)   : {CONFIG.min_result_delay:.2f} s")
        print(f"  [5] Таймаут очистки (CLEAR_STATUS)       : {CONFIG.clear_status_timeout:.2f} s")
        print(f"  [6] Пауза после очистки (AFTER_CLEAR)    : {CONFIG.after_clear_delay:.2f} s")
        print(f"  [7] Пауза между никами (BETWEEN)         : {CONFIG.between_usernames:.2f} s")
        print(f"  [8] Повторы при UNKNOWN (RETRIES)        : {CONFIG.retries}")
        print(f"  [9] Сбросить по умолчанию")
        print(f"  [0] Назад")
        print(c("─" * 68, Style.DIM))

        choice = input("  Параметр > ").strip()

        if choice == "0" or not choice:
            break
        elif choice == "1":
            val = input("  Имя входного файла: ").strip()
            if val:
                CONFIG.input_file = val
        elif choice == "2":
            _update_float("RESULT_TIMEOUT", "result_timeout")
        elif choice == "3":
            _update_float("POLL_INTERVAL", "poll_interval")
        elif choice == "4":
            _update_float("MIN_RESULT_DELAY", "min_result_delay")
        elif choice == "5":
            _update_float("CLEAR_STATUS_TIMEOUT", "clear_status_timeout")
        elif choice == "6":
            _update_float("AFTER_CLEAR_DELAY", "after_clear_delay")
        elif choice == "7":
            _update_float("BETWEEN_USERNAMES", "between_usernames")
        elif choice == "8":
            val = input("  Количество повторов (>= 0): ").strip()
            try:
                num = int(val)
                if num >= 0:
                    CONFIG.retries = num
            except ValueError:
                pass
        elif choice == "9":
            defaults = Config()
            for field in defaults.__dataclass_fields__:
                setattr(CONFIG, field, getattr(defaults, field))


def _update_float(label: str, attr: str) -> None:
    val = input(f"  Новое значение {label} (сек): ").strip().replace(",", ".")
    try:
        num = float(val)
        if num >= 0:
            setattr(CONFIG, attr, num)
    except ValueError:
        pass


def interactive_menu() -> None:
    ensure_input_file_exists()

    while True:
        clear_screen()
        valid, invalid = load_usernames()
        tg_status = get_telegram_status_summary()
        latest_free = get_latest_free_file()

        print_header("Telegram Desktop UIA Checker")
        print(f"  Telegram     : {tg_status}")
        print(
            f"  Список       : {get_input_path().name} "
            f"{c(f'(валидных: {len(valid)}, невалидных: {len(invalid)})', Style.DIM)}"
        )
        print(
            f"  Вывод        : {latest_free.name if latest_free else c('нет', Style.DIM)}"
        )
        print(c("─" * 68, Style.DIM))
        print("  [1] Запустить проверку")
        print("  [2] Проверить подключение к Telegram")
        print("  [3] Редактировать usernames.txt")
        print("  [4] Настройки таймингов")
        print("  [5] Просмотр найденных (free.txt)")
        print("  [0] Выход")
        print(c("─" * 68, Style.DIM))

        try:
            choice = input("  Выбор > ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if choice == "1":
            run_checker()
        elif choice == "2":
            check_connection_screen()
        elif choice == "3":
            open_usernames_file()
        elif choice == "4":
            settings_menu()
        elif choice == "5":
            view_free_results()
        elif choice == "0":
            break


def main() -> None:
    init_console()
    if "--auto" in sys.argv:
        run_checker()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()

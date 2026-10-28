<div align="center">

# Telegram Username Checker

**A fast, desktop-native username availability checker for Windows.**  
*No API credentials. No Telethon/Pyrogram sessions. Just Telegram Desktop.*

<p>
  <a href="#русский">Русский</a> · <a href="#english">English</a>
</p>

<p>
  <a href="https://github.com/forevertempest/TelegramDekstop-UsernameCheck/stargazers"><img src="https://img.shields.io/github/stars/forevertempest/TelegramDekstop-UsernameCheck?style=for-the-badge&logo=github&label=STARS" alt="GitHub stars"></a>
  <a href="https://github.com/forevertempest/TelegramDekstop-UsernameCheck/blob/main/LICENSE"><img src="https://img.shields.io/github/license/forevertempest/TelegramDekstop-UsernameCheck?style=for-the-badge&label=LICENSE" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10 or newer">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
</p>

<sub>Version 1.0.0 · Built with Python, Win32 API & UI Automation</sub>

</div>

---

## Навигация

- [Русский](#русский)
  - [Обзор](#обзор)
  - [Возможности](#возможности)
  - [Как это работает](#как-это-работает)
  - [Установка](#установка)
  - [Использование](#использование)
  - [Статусы проверки](#статусы-проверки)
  - [Настройки](#настройки)
  - [Решение проблем](#решение-проблем)
  - [Конфиденциальность и ограничения](#конфиденциальность-и-ограничения)
- [English](#english)
  - [Overview](#overview)
  - [Features](#features)
  - [How it works](#how-it-works)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Check statuses](#check-statuses)
  - [Configuration](#configuration)
  - [Troubleshooting](#troubleshooting)
  - [Privacy & limitations](#privacy--limitations)

---

# Русский

## Обзор

**Telegram Username Checker** — инструмент для пакетной проверки доступности Telegram-юзернеймов через интерфейс **Telegram Desktop** на Windows.

Вместо Telegram API и сторонних клиентских библиотек программа взаимодействует с открытым окном Telegram Desktop: отправляет текст в поле `@username` через Win32-сообщения и считывает ответ из UI Automation-дерева окна.

> **Главная идея:** проверять списки юзернеймов напрямую через установленный Telegram Desktop — без `api_id`, `api_hash`, Telethon, Pyrogram и файлов сессий.

## Возможности

<table>
  <tr>
    <td width="50%">
      <strong>⚡ Быстрая пакетная проверка</strong><br>
      Обрабатывает список имён последовательно, показывает статус, время ответа и текущую скорость.
    </td>
    <td width="50%">
      <strong>🖥️ Работа через Telegram Desktop</strong><br>
      Использует Win32 API и UI Automation вместо отдельного Telegram-клиента.
    </td>
  </tr>
  <tr>
    <td>
      <strong>🧹 Подготовка списка</strong><br>
      Убирает `@` и ссылки <code>t.me</code>, игнорирует пустые строки и комментарии, удаляет дубликаты.
    </td>
    <td>
      <strong>💾 Сохранение результатов</strong><br>
      Каждый найденный свободный юзернейм записывается в файл сразу после обнаружения.
    </td>
  </tr>
  <tr>
    <td>
      <strong>🌐 RU / EN статусы Telegram</strong><br>
      Распознаёт ответы интерфейса на русском и английском языках.
    </td>
    <td>
      <strong>🎛️ Интерактивное меню</strong><br>
      Диагностика подключения, редактирование списка, настройка таймингов и просмотр результатов.
    </td>
  </tr>
</table>

## Как это работает

```text
  usernames.txt
       │
       ▼
  Нормализация и проверка формата
  • удаление @ и префикса t.me
  • фильтрация дубликатов
  • локальная проверка имени
       │
       ▼
  Поиск Telegram.exe и поля @username
       │
       ▼
  Win32 PostMessage ──► Telegram Desktop
       │                     │
       │                     ▼
       │              Ответ интерфейса
       │                     │
       ◄──── UI Automation / pywinauto
       │
       ▼
  Определение статуса и статистика
       │
       ├── FREE ───────► free.txt
       ├── TAKEN
       ├── FRAGMENT
       ├── INVALID
       ├── RATE_LIMIT
       └── UNKNOWN
```

1. **Подготовка.** Программа читает `usernames.txt`, нормализует записи, удаляет дубликаты без учёта регистра и отбрасывает некорректные имена.
2. **Подключение к окну.** Находит процесс `Telegram.exe` и поле ввода `@username` с помощью `pywinauto` (UI Automation).
3. **Ввод.** Отправляет символы и клавиши непосредственно в окно с помощью Win32 `PostMessage` (`WM_CHAR`, `WM_KEYDOWN`, `WM_KEYUP`).
4. **Чтение ответа.** Анализирует текстовые UIA-элементы Telegram и определяет статус имени.
5. **Сохранение.** Статус `FREE` немедленно записывается в следующий доступный файл `free*.txt`.

## Установка

### Требования

- Windows;
- [Telegram Desktop](https://desktop.telegram.org/);
- Python **3.10 или новее**.

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/forevertempest/TelegramDekstop-UsernameCheck.git
cd TelegramDekstop-UsernameCheck
```

### 2. Установите зависимости

Рекомендуется использовать виртуальное окружение:

```bash
py -m venv .venv
.venv\Scripts\activate
py -m pip install --upgrade pip
pip install -r requirements.txt
```

Или установите зависимости напрямую:

```bash
py -m pip install -r requirements.txt
```

## Использование

### 1. Подготовьте список юзернеймов

При первом запуске программа автоматически создаст `usernames.txt`, если файла ещё нет. Добавьте имена — по одному на строку.

```text
telegram
@username
https://t.me/example_name
https://t.me/another_name?start=hello
```

Поддерживаются обычные имена, формат `@username` и ссылки `t.me`. Пустые строки, строки-комментарии с `#` и повторяющиеся имена игнорируются. Локальная проверка скрипта принимает имена длиной 5–32 символа: первый символ — латинская буква, последний — буква или цифра; разрешены латинские буквы, цифры и `_`, но не два подчёркивания подряд.

### 2. Откройте нужное поле в Telegram Desktop

Запустите Telegram Desktop и откройте окно, в котором доступно поле `@username`:

- **Настройки → Мой аккаунт → Имя пользователя**;
- настройки публичной ссылки при создании или редактировании канала/группы.

**Оставьте это окно открытым.** Не закрывайте диалог до завершения проверки.

### 3. Запустите программу

```bash
py checker.py
```

Откроется интерактивное меню (в текущей версии его подписи на русском языке). Основные пункты:

| Пункт | Действие |
|:--:|---|
| `1` | Запустить проверку списка |
| `2` | Проверить подключение к Telegram Desktop |
| `3` | Открыть `usernames.txt` в Блокноте |
| `4` | Изменить настройки таймингов |
| `5` | Просмотреть найденные свободные имена |
| `0` | Выход |

**Автоматический запуск без меню:**

```bash
py checker.py --auto
```

Для остановки текущей проверки нажмите `Ctrl+C`. Программа завершит цикл и выведет итоговую статистику.

### Результаты

Свободные имена сохраняются по мере обнаружения, поэтому результаты не теряются при обычной остановке проверки:

```text
free.txt
free1.txt
free2.txt
...
```

Существующие файлы не перезаписываются: программа выбирает следующее свободное имя файла. В результаты попадают только записи со статусом `FREE`.

## Статусы проверки

| Статус | Значение |
|---|---|
| <code>✅ FREE</code> | Имя доступно — сохраняется в файл результатов. |
| <code>❌ TAKEN</code> | Имя уже занято. |
| <code>💎 FRAGMENT</code> | Имя связано с предложением о покупке через Fragment; это не обычный свободный юзернейм. |
| <code>⚠️ INVALID</code> | Имя не прошло локальную проверку формата или Telegram сообщил, что оно некорректно. |
| <code>⏳ RATE_LIMIT</code> | Telegram сообщил о временном ограничении попыток. |
| <code>❓ UNKNOWN</code> | За отведённое время программа не получила распознанный ответ. |

`UNKNOWN` не означает, что имя занято или свободно. При медленном соединении увеличьте `result_timeout` в настройках и повторите проверку.

## Настройки

Параметры доступны в пункте **«Настройки таймингов»** интерактивного меню.

| Параметр в коде | По умолчанию | Назначение |
|---|---:|---|
| `input_file` | `usernames.txt` | Имя входного файла со списком. |
| `result_timeout` | `0.30` сек | Максимальное время ожидания распознанного ответа. |
| `poll_interval` | `0.19` сек | Интервал опроса UI-элементов. |
| `min_result_delay` | `0.19` сек | Минимальная задержка перед чтением статуса. |
| `clear_status_timeout` | `0.22` сек | Время ожидания исчезновения предыдущего статуса. |
| `after_clear_delay` | `0.15` сек | Пауза после очистки поля перед новым вводом. |
| `between_usernames` | `0.15` сек | Пауза между проверками. |
| `retries` | `0` | Число повторных попыток при `UNKNOWN`. |

Значения можно менять прямо в меню. Изменения действуют в текущем запуске программы и не сохраняются как постоянный конфигурационный файл. Для возврата к исходным значениям используйте пункт **«Сбросить по умолчанию»**.

## Решение проблем

<details>
  <summary><strong>Telegram Desktop не найден</strong></summary>

  Убедитесь, что Telegram Desktop запущен и процесс `Telegram.exe` доступен в системе.
</details>

<details>
  <summary><strong>Не найдено поле @username</strong></summary>

  Откройте настройки имени пользователя или настройки публичной ссылки канала/группы. Убедитесь, что нужное диалоговое окно открыто и поле `@username` отображается в Telegram Desktop.
</details>

<details>
  <summary><strong>Часто появляется UNKNOWN</strong></summary>

  Увеличьте `result_timeout` в настройках. Также проверьте соединение и убедитесь, что Telegram успевает обновлять состояние поля.
</details>

<details>
  <summary><strong>Появился RATE_LIMIT</strong></summary>

  Это ответ Telegram о временном ограничении. Сделайте паузу и не пытайтесь обходить ограничение увеличением интенсивности запросов.
</details>

## Конфиденциальность и ограничения

- Программа не требует `api_id`, `api_hash`, Telethon/Pyrogram и файлов сессий.
- Список имён и текстовые результаты обрабатываются локально; отдельный сервер проекта для них не используется.
- Проверка всё равно обращается к Telegram через обычный интерфейс Telegram Desktop: передаваемые имена обрабатываются сервисом Telegram.
- Telegram может применять ограничения частоты запросов. Программа не гарантирует отсутствие `RATE_LIMIT`, ограничений аккаунта или изменений в интерфейсе.
- Работа зависит от текущей структуры окна Telegram Desktop. После обновлений приложения поиск поля или распознавание текста может потребовать адаптации.

Используйте инструмент ответственно и соблюдайте правила Telegram. Проект не связан с Telegram и не является его официальным продуктом.

---

# English

## Overview

**Telegram Username Checker** is a batch username availability checker for **Telegram Desktop on Windows**.

Instead of connecting through the Telegram API or third-party client libraries, it interacts with the running Telegram Desktop window: input is sent to the `@username` field through Win32 messages, while the resulting status is read from the window's UI Automation tree.

> **The idea:** check username lists through the official desktop application — without `api_id`, `api_hash`, Telethon, Pyrogram, or client session files.

## Features

<table>
  <tr>
    <td width="50%">
      <strong>⚡ Batch processing</strong><br>
      Checks usernames one by one and displays each result, response time, and current throughput.
    </td>
    <td width="50%">
      <strong>🖥️ Telegram Desktop integration</strong><br>
      Uses the Win32 API and UI Automation instead of a separate Telegram client.
    </td>
  </tr>
  <tr>
    <td>
      <strong>🧹 Input normalization</strong><br>
      Removes <code>@</code> and <code>t.me</code> prefixes, ignores blank lines and comments, and filters duplicates.
    </td>
    <td>
      <strong>💾 Live result saving</strong><br>
      Every available username is written to disk as soon as it is detected.
    </td>
  </tr>
  <tr>
    <td>
      <strong>🌐 Russian & English status parsing</strong><br>
      Recognizes supported Telegram UI messages in both languages.
    </td>
    <td>
      <strong>🎛️ Interactive console menu</strong><br>
      Connection diagnostics, input editing, timing controls, and result browsing.
    </td>
  </tr>
</table>

## How it works

```text
  usernames.txt
       │
       ▼
  Normalize and validate input
  • remove @ and t.me prefixes
  • filter duplicates
  • validate username format locally
       │
       ▼
  Find Telegram.exe and the @username field
       │
       ▼
  Win32 PostMessage ──► Telegram Desktop
       │                     │
       │                     ▼
       │                UI response
       │                     │
       ◄──── UI Automation / pywinauto
       │
       ▼
  Parse status and update statistics
       │
       ├── FREE ───────► free.txt
       ├── TAKEN
       ├── FRAGMENT
       ├── INVALID
       ├── RATE_LIMIT
       └── UNKNOWN
```

1. **Prepare input.** Reads `usernames.txt`, normalizes entries, removes case-insensitive duplicates, and filters invalid names locally.
2. **Connect to the window.** Finds the `Telegram.exe` process and its `@username` input control using `pywinauto` (UI Automation).
3. **Enter a username.** Sends characters and key messages directly to the window through Win32 `PostMessage` (`WM_CHAR`, `WM_KEYDOWN`, `WM_KEYUP`).
4. **Read the response.** Inspects Telegram's UIA text elements and classifies the displayed status.
5. **Save available names.** Writes every `FREE` result to the next available `free*.txt` file immediately.

## Installation

### Requirements

- Windows;
- [Telegram Desktop](https://desktop.telegram.org/);
- Python **3.10 or newer**.

### 1. Clone the repository

```bash
git clone https://github.com/forevertempest/TelegramDekstop-UsernameCheck.git
cd TelegramDekstop-UsernameCheck
```

### 2. Install dependencies

Using a virtual environment is recommended:

```bash
py -m venv .venv
.venv\Scripts\activate
py -m pip install --upgrade pip
pip install -r requirements.txt
```

Or install the dependencies directly:

```bash
py -m pip install -r requirements.txt
```

## Usage

### 1. Prepare your username list

On the first run, the program automatically creates `usernames.txt` if it does not exist. Add one entry per line.

```text
telegram
@username
https://t.me/example_name
https://t.me/another_name?start=hello
```

Plain usernames, `@username` entries, and `t.me` links are supported. Blank lines, `#` comments, and duplicate names are ignored. The local validator accepts 5–32 characters: the first character must be a Latin letter, the last must be a letter or digit; only Latin letters, digits, and `_` are allowed, with no consecutive underscores.

### 2. Open the username field in Telegram Desktop

Launch Telegram Desktop and open a screen containing the `@username` field:

- **Settings → My Account → Username**;
- public-link settings while creating or editing a channel/group.

**Keep this dialog open** until the check is complete.

### 3. Run the checker

```bash
py checker.py
```

The interactive menu (currently labelled in Russian) provides the following actions:

| Option | Action |
|:--:|---|
| `1` | Start checking the list |
| `2` | Test the Telegram Desktop connection |
| `3` | Open `usernames.txt` in Notepad |
| `4` | Adjust timing settings |
| `5` | View available usernames |
| `0` | Exit |

**Run the checker without the menu:**

```bash
py checker.py --auto
```

Press `Ctrl+C` to stop an active check. The program will finish the loop and print the summary.

### Results

Available usernames are saved as soon as they are detected, so results are preserved during a normal interruption:

```text
free.txt
free1.txt
free2.txt
...
```

Existing files are not overwritten. The checker picks the next available filename and stores only entries with the `FREE` status.

## Check statuses

| Status | Meaning |
|---|---|
| <code>✅ FREE</code> | The username is available and is saved to the output file. |
| <code>❌ TAKEN</code> | The username is already taken. |
| <code>💎 FRAGMENT</code> | The name is associated with an offer to purchase it through Fragment; it is not an ordinary available username. |
| <code>⚠️ INVALID</code> | The name failed local format validation or Telegram reported it as invalid. |
| <code>⏳ RATE_LIMIT</code> | Telegram reported a temporary attempt limit. |
| <code>❓ UNKNOWN</code> | No recognizable response was received within the configured timeout. |

`UNKNOWN` does **not** mean that a username is either available or taken. If the connection is slow, increase `result_timeout` in the settings and check again.

## Configuration

Timing parameters can be adjusted from **Timing Settings** in the interactive menu.

| Code setting | Default | Description |
|---|---:|---|
| `input_file` | `usernames.txt` | Input file containing the username list. |
| `result_timeout` | `0.30` sec | Maximum time to wait for a recognizable response. |
| `poll_interval` | `0.19` sec | Interval between UI element polls. |
| `min_result_delay` | `0.19` sec | Minimum delay before reading a status. |
| `clear_status_timeout` | `0.22` sec | Time allowed for the previous status to disappear. |
| `after_clear_delay` | `0.15` sec | Pause after clearing the field and before typing the next name. |
| `between_usernames` | `0.15` sec | Delay between username checks. |
| `retries` | `0` | Number of retries after an `UNKNOWN` result. |

Changes made in the menu apply to the current program run and are not saved to a persistent configuration file. Use **Reset to defaults** to restore the original values.

## Troubleshooting

<details>
  <summary><strong>Telegram Desktop was not found</strong></summary>

  Make sure Telegram Desktop is running and that its `Telegram.exe` process is available.
</details>

<details>
  <summary><strong>The @username field was not found</strong></summary>

  Open the username settings or the public-link settings for a channel/group. Make sure the relevant dialog is open and the `@username` field is visible in Telegram Desktop.
</details>

<details>
  <summary><strong>UNKNOWN appears frequently</strong></summary>

  Increase `result_timeout` in the settings. Check your connection and make sure Telegram has enough time to update the field state.
</details>

<details>
  <summary><strong>RATE_LIMIT was returned</strong></summary>

  Telegram has reported a temporary limit. Pause the checks; do not try to bypass the limit by increasing the request intensity.
</details>

## Privacy & limitations

- No `api_id`, `api_hash`, Telethon/Pyrogram dependency, or client session files are required.
- The input list and text results are processed locally; this project does not use its own server to handle them.
- The checker still communicates with Telegram through the regular Telegram Desktop interface. Usernames entered into the app are processed by Telegram.
- Telegram may enforce rate limits. The tool cannot guarantee that `RATE_LIMIT`, account restrictions, or UI changes will never occur.
- The checker depends on Telegram Desktop's current window structure. Application updates may require changes to control discovery or text parsing.

Use this tool responsibly and follow Telegram's rules. This is an independent project and is not affiliated with or endorsed by Telegram.

---

<div align="center">

**Made by [forevertempest](https://github.com/forevertempest)**

[Repository](https://github.com/forevertempest/TelegramDekstop-UsernameCheck) · [Issues](https://github.com/forevertempest/TelegramDekstop-UsernameCheck/issues) · [MIT License](LICENSE)

</div>

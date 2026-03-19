from __future__ import annotations

from config import settings


def ensure_promos_file() -> None:
    """Создать файл акций, если его нет."""
    try:
        with open(settings.PROMOS_FILE, "a", encoding="utf-8"):
            pass
    except Exception:
        # Не валим бота — при ошибке чтения вернём сообщение
        pass


def read_promos_text() -> str:
    """Прочитать акции из файла и вернуть текст для пользователя."""
    ensure_promos_file()
    try:
        with open(settings.PROMOS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception:
        return "🎁 Сейчас акции недоступны (ошибка чтения файла)."

    if not content:
        return "🎁 Акций пока нет."
    return "🎁 Акции:\n" + content


def add_promo_line(line_text: str) -> None:
    """Добавить акцию строкой в файл."""
    ensure_promos_file()
    with open(settings.PROMOS_FILE, "a", encoding="utf-8") as f:
        if not line_text.endswith("\n"):
            line_text += "\n"
        f.write(line_text)


def delete_promo_line(line_number: int) -> tuple[bool, int]:
    """Удалить строку по номеру (1..N) из promos.txt."""
    ensure_promos_file()
    with open(settings.PROMOS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    idx = line_number - 1
    if idx < 0 or idx >= len(lines):
        return False, len(lines)

    del lines[idx]
    with open(settings.PROMOS_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True, len(lines)


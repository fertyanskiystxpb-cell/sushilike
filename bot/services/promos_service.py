from __future__ import annotations

from config import settings


def read_promos_text() -> str:
    """Прочитать акции из БД и вернуть текст для пользователя."""
    if not getattr(settings, 'DB_ENABLED', False):
        # Fallback к файлу, если БД отключена
        return _read_promos_from_file()
    
    try:
        from database.models import list_promo_lines
        lines = list_promo_lines()
        if not lines:
            return "🎁 Акций пока нет."
        return "🎁 Акции:\n" + "\n".join(lines)
    except Exception:
        return "🎁 Сейчас акции недоступны (ошибка чтения БД)."


def add_promo_line(line_text: str) -> None:
    """Добавить акцию в БД."""
    if not getattr(settings, 'DB_ENABLED', False):
        # Fallback к файлу, если БД отключена
        _add_promo_line_to_file(line_text)
        return
    
    try:
        from database.models import add_promo_line_db
        add_promo_line_db(line_text)
    except Exception:
        pass


def delete_promo_line(line_number: int) -> tuple[bool, int]:
    """Удалить строку по номеру (1..N) из БД."""
    if not getattr(settings, 'DB_ENABLED', False):
        # Fallback к файлу, если БД отключена
        return _delete_promo_line_from_file(line_number)
    
    try:
        from database.models import delete_promo_line_db
        return delete_promo_line_db(line_number)
    except Exception:
        return False, 0


def _read_promos_from_file() -> str:
    """Fallback: прочитать акции из файла."""
    try:
        with open(settings.PROMOS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception:
        return "🎁 Сейчас акции недоступны (ошибка чтения файла)."

    if not content:
        return "🎁 Акций пока нет."
    return "🎁 Акции:\n" + content


def _add_promo_line_to_file(line_text: str) -> None:
    """Fallback: добавить акцию в файл."""
    try:
        with open(settings.PROMOS_FILE, "a", encoding="utf-8") as f:
            if not line_text.endswith("\n"):
                line_text += "\n"
            f.write(line_text)
    except Exception:
        pass


def _delete_promo_line_from_file(line_number: int) -> tuple[bool, int]:
    """Fallback: удалить строку из файла."""
    try:
        with open(settings.PROMOS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        idx = line_number - 1
        if idx < 0 or idx >= len(lines):
            return False, len(lines)

        del lines[idx]
        with open(settings.PROMOS_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True, len(lines)
    except Exception:
        return False, 0


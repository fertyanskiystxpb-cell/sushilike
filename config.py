from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Централизованная конфигурация бота.

    ВАЖНО:
    - значения читаются из переменных окружения (или из .env)
    - не выводить/не логировать чувствительные значения (токены)
    """

    # ВК / bot_longpoll
    VK_GROUP_TOKEN: str = Field(
        ...,
        validation_alias=AliasChoices("VK_GROUP_TOKEN", "GROUP_TOKEN"),
        description="Токен сообщества ВК (vk_api).",
    )
    VK_GROUP_ID: int = Field(
        ...,
        validation_alias=AliasChoices("VK_GROUP_ID", "GROUP_ID"),
        description="ID сообщества ВК (число).",
    )
    VK_ADMIN_ID: int = Field(
        ...,
        validation_alias=AliasChoices("VK_ADMIN_ID", "ADMIN_ID"),
        description="ID администратора (основной).",
    )
    VK_ADMIN_IDS: str = Field(
        default="",
        validation_alias=AliasChoices("VK_ADMIN_IDS", "ADMIN_IDS"),
        description="ID администраторов через запятую (например: 123,456,789). Если пусто — используется VK_ADMIN_ID.",
    )

    # Реквизиты для перевода (предоплата переводом)
    PAYMENT_BANK: str = Field(
        ...,
        validation_alias=AliasChoices("PAYMENT_BANK", "AYMENT_BANK"),
        description="Название банка.",
    )
    PAYMENT_ACCOUNT_NUMBER: str = Field(
        ...,
        description="Номер карты/счёта.",
    )
    PAYMENT_RECEIVER_NAME: str = Field(
        ...,
        description="Получатель перевода.",
    )

    # Доп. параметры (не секреты, но удобно выносить)
    PROMOS_FILE: str = Field(default="promos.txt", description="Файл с акциями.")
    GROUP_WALL_URL: str = Field(
        default="https://vk.com/wall-236800094",
        description="Ссылка для кнопки 'Акции' (open_link).",
    )

    # Адрес заведения
    ORDER_ADDRESS_TEXT: str = Field(
        default="Куйбышева 8\nДверь слева рядом с нашим указателем.",
        description="Текст адреса для сообщения пользователю.",
    )

    # Зона доставки (опционально — показывается при вводе адреса)
    DELIVERY_ZONE_HINT: str = Field(
        default="",
        description="Подсказка по зоне доставки, напр. 'доставляем по городу N'.",
    )

    # Часовой пояс для времени работы (смещение от UTC)
    TIMEZONE_OFFSET_HOURS: int = Field(
        default=5,
        description="Часовой пояс доставки (UTC+N).",
    )

    # Stub DB (по требованию: DB_DISABLED по умолчанию)
    DB_ENABLED: bool = Field(default=False, description="Сохранять заказы в SQLite (по умолчанию False).")
    DB_PATH: str = Field(default="sushi_like.db", description="Путь к sqlite db файл (если DB_ENABLED=True).")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


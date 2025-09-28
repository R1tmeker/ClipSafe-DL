from __future__ import annotations

import logging

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import Settings
from .jobs import JobQueue
from .models import Job, JobType
from .texts import (
    HELP_MESSAGE,
    START_MESSAGE,
    YTDL_REFUSAL_MESSAGE,
)
from .validators import classify_url, ensure_allowed_url

logger = logging.getLogger(__name__)

OPERATIONS_KEYBOARD = (
    ("Оставить оригинал", "op:original"),
    ("Ремукс", "op:remux"),
    ("Вырезать", "op:trim"),
    ("Аудио", "op:audio"),
    ("Превью", "op:preview"),
)


def _get_settings(message: Message) -> Settings:
    return message.bot["settings"]


def _get_queue(message: Message) -> JobQueue:
    return message.bot["job_queue"]


def _build_operations_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for title, payload in OPERATIONS_KEYBOARD:
        builder.button(text=title, callback_data=payload)
    builder.adjust(1, 2, 2)
    return builder.as_markup()


router = Router()


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(START_MESSAGE)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(HELP_MESSAGE)


@router.message(Command("upload"))
async def handle_upload(message: Message) -> None:
    settings = _get_settings(message)
    await message.answer(
        (
            "Пришлите файл до "
            f"{settings.max_file_gb} ГБ и длительностью до {settings.max_duration_hours} часов. "
            "После загрузки выберите нужную операцию."
        ),
        reply_markup=_build_operations_keyboard(),
    )


@router.message(Command("link"))
async def handle_link_hint(message: Message) -> None:
    await message.answer("Пришлите прямую ссылку на файл. Я проверю заголовки и предложу опции.")


@router.message(Command("format"))
async def handle_format(message: Message) -> None:
    await message.answer(
        (
            "Выберите контейнер вывода: MP4 или MKV. "
            "MP4 требует совместимых кодеков. При несовместимости предложу MKV."
        )
    )


@router.message(Command("queue"))
async def handle_queue(message: Message) -> None:
    queue = _get_queue(message)
    jobs = await queue.list_user_jobs(message.from_user.id, limit=5)
    if not jobs:
        await message.answer("Активных задач нет.")
        return

    lines = [
        f"#{job.id[:6]} · {job.type.value} · {job.status.value} · создано {job.created_at:%H:%M}"
        for job in jobs
    ]
    await message.answer("\n".join(lines))


@router.message(Command("cancel"))
async def handle_cancel(message: Message) -> None:
    queue = _get_queue(message)
    cancelled = await queue.cancel_latest_job(message.from_user.id)
    if not cancelled:
        await message.answer("Нет задачи для отмены.")
    else:
        await message.answer(f"Отменил #{cancelled.id[:6]} ({cancelled.type.value}).")


@router.message(F.text.startswith("http"))
async def handle_url(message: Message) -> None:
    queue = _get_queue(message)
    settings = _get_settings(message)
    url = message.text.strip()
    url_info = classify_url(url)

    if url_info.is_platform_restricted:
        await message.answer(YTDL_REFUSAL_MESSAGE)
        return

    validation = await ensure_allowed_url(url, settings)
    if not validation.ok:
        await message.answer(f"Не получается обработать ссылку: {validation.reason}")
        return

    job = Job.from_url(
        user_id=message.from_user.id,
        url=url,
        media_info=validation.meta,
    )
    await queue.enqueue(job)
    await message.answer(
        "Ссылка принята. Какую операцию выполнить?",
        reply_markup=_build_operations_keyboard(),
    )


@router.message(F.document | F.video)
async def handle_file(message: Message) -> None:
    queue = _get_queue(message)
    settings = _get_settings(message)
    file = message.document or message.video
    if not file:
        await message.answer("Не удалось прочитать файл. Попробуйте ещё раз.")
        return

    size = file.file_size or 0
    if size > settings.max_file_bytes:
        await message.answer("Файл превышает допустимый лимит.")
        return

    job = Job.from_file(
        user_id=message.from_user.id,
        file_id=file.file_id,
        file_name=file.file_name,
        file_size=size,
        mime_type=file.mime_type,
    )
    await queue.enqueue(job)
    await message.answer(
        "Файл сохранён. Выберите операцию:",
        reply_markup=_build_operations_keyboard(),
    )


@router.callback_query(F.data.startswith("op:"))
async def handle_operation_choice(callback: CallbackQuery) -> None:
    queue: JobQueue = callback.message.bot["job_queue"]
    mapping = {
        "op:original": JobType.ORIGINAL,
        "op:remux": JobType.REMUX,
        "op:trim": JobType.TRIM,
        "op:audio": JobType.AUDIO,
        "op:preview": JobType.PREVIEW,
    }
    job_type = mapping.get(callback.data)
    if not job_type:
        await callback.answer("Неизвестная команда", show_alert=True)
        return

    job = await queue.assign_latest_job(callback.from_user.id, job_type)
    if not job:
        await callback.answer("Нет активной загрузки", show_alert=True)
        return

    await callback.message.answer(
        f"Задача #{job.id[:6]} поставлена в очередь (операция: {job_type.value})."
    )
    await callback.answer()


def create_dispatcher(settings: Settings, queue: JobQueue) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher

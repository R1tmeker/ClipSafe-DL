from __future__ import annotations

import logging
from typing import Optional

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import Settings
from .jobs import JobQueue
from .models import Job, JobType
from .states import RightsStates
from .texts import (
    HELP_MESSAGE,
    MP4_INCOMPATIBLE_MESSAGE,
    RIGHTS_CONFIRMED_MESSAGE,
    RIGHTS_DECLINED_MESSAGE,
    RIGHTS_PROMPT_MESSAGE,
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

RIGHTS_CALLBACK_PREFIX = "rights"


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


def _build_rights_keyboard(job_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, у меня есть права", callback_data=f"{RIGHTS_CALLBACK_PREFIX}:yes:{job_id}")
    builder.button(text="Отменить", callback_data=f"{RIGHTS_CALLBACK_PREFIX}:no:{job_id}")
    builder.adjust(1, 1)
    return builder.as_markup()


async def _register_pending_job(state: FSMContext, job_id: str) -> None:
    data = await state.get_data()
    pending = data.get("pending_jobs", [])
    if job_id not in pending:
        pending.append(job_id)
    await state.update_data(pending_jobs=pending)
    await state.set_state(RightsStates.waiting_confirmation)


async def _remove_pending_job(state: FSMContext, job_id: str) -> None:
    data = await state.get_data()
    pending = data.get("pending_jobs", [])
    if job_id in pending:
        pending.remove(job_id)
    if pending:
        await state.update_data(pending_jobs=pending)
    else:
        await state.clear()


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
            "После загрузки подтвердите права и выберите нужную операцию."
        )
    )


@router.message(Command("link"))
async def handle_link_hint(message: Message) -> None:
    await message.answer("Пришлите прямую ссылку на файл. Я проверю заголовки и попрошу подтвердить права.")


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
async def handle_url(message: Message, state: FSMContext) -> None:
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
    await _register_pending_job(state, job.id)
    await message.answer(RIGHTS_PROMPT_MESSAGE, reply_markup=_build_rights_keyboard(job.id))


@router.message(F.document | F.video)
async def handle_file(message: Message, state: FSMContext) -> None:
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
    await _register_pending_job(state, job.id)
    await message.answer(RIGHTS_PROMPT_MESSAGE, reply_markup=_build_rights_keyboard(job.id))


@router.callback_query(RightsStates.waiting_confirmation, F.data.startswith(f"{RIGHTS_CALLBACK_PREFIX}:"))
async def handle_rights_confirmation(
    callback: CallbackQuery,
    state: FSMContext,
    queue: JobQueue,
) -> None:
    if not callback.data:
        await callback.answer()
        return
    _, decision, job_id = callback.data.split(":", maxsplit=2)

    job = await queue.get_job(job_id)
    if not job:
        await callback.answer("Задача не найдена", show_alert=True)
        await _remove_pending_job(state, job_id)
        return

    if decision == "yes":
        job.params["rights_confirmed"] = True
        await queue.update_job(job)
        await _remove_pending_job(state, job_id)
        await callback.message.answer(RIGHTS_CONFIRMED_MESSAGE, reply_markup=_build_operations_keyboard())
        await callback.answer("Права подтверждены")
    else:
        await queue.delete_job(job_id)
        await _remove_pending_job(state, job_id)
        await callback.message.answer(RIGHTS_DECLINED_MESSAGE)
        await callback.answer("Задача отменена")


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
    if not job:\n        await callback.answer("Сначала подтвердите права или загрузите файл", show_alert=True)\n        return\n\n    if not job.params.get("rights_confirmed"):\n        await callback.answer("Сначала подтвердите права", show_alert=True)\n        await queue.enqueue(job)\n        return\n
    if job_type == JobType.REMUX and job.params.get("target_container") == "mp4" and job.mime_type and "opus" in (job.mime_type or "").lower():
        await callback.message.answer(MP4_INCOMPATIBLE_MESSAGE)

    await callback.message.answer(
        f"Задача #{job.id[:6]} поставлена в очередь (операция: {job_type.value})."
    )
    await callback.answer()


def create_dispatcher(settings: Settings, queue: JobQueue) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher



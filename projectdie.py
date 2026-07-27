import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "TOKEN"

bot = Bot(token=TOKEN)
dp = Dispatcher()

targets = {}
users = {}
stats = {}
settings = {}
blacklists = {}

def get_user_stats(user_id: int):
    if user_id not in stats:
        stats[user_id] = {"sent": 0, "received": 0}
    return stats[user_id]

def is_accepting(user_id: int) -> bool:
    return settings.get(user_id, {}).get("active", True)

def get_main_kb(user_id: int):
    active = is_accepting(user_id)
    status_label = "Прием: Вкл" if active else "Прием: Выкл"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать ссылку", callback_data="make_link")],
        [
            InlineKeyboardButton(text="Профиль", callback_data="profile"),
            InlineKeyboardButton(text=status_label, callback_data="toggle_status")
        ],
        [InlineKeyboardButton(text="Инструкция", callback_data="help")]
    ])

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="В меню", callback_data="main_menu")]
    ])

@dp.message(CommandStart())
async def start_cmd(message: types.Message, command: CommandObject):
    user = message.from_user
    if user.username:
        users[user.username.lower()] = user.id

    args = command.args
    if args:
        target_id = None
        if args.isdigit():
            target_id = int(args)
        else:
            target_id = users.get(args.lower().lstrip("@"))

        if target_id == user.id:
            await message.answer("Нельзя отправлять сообщения самому себе.")
            return

        if target_id:
            if not is_accepting(target_id):
                await message.answer("Этот пользователь временно отключил прием сообщений.")
                return
                
            if user.id in blacklists.get(target_id, set()):
                await message.answer("Вы не можете отправлять сообщения этому пользователю.")
                return

            targets[user.id] = target_id
            await message.answer("Напишите сообщение, и я передам его анонимно.")
            return
        else:
            await message.answer("Пользователь не найден. Возможно, бот перезапускался.")

    await message.answer(
        "Привет! С помощью этого бота можно получать и отправлять анонимные сообщения.\n\n"
        "Выберите нужное действие ниже:",
        reply_markup=get_main_kb(user.id)
    )

@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Главное меню бота:",
        reply_markup=get_main_kb(callback.from_user.id)
    )
    await callback.answer()

@dp.callback_query(F.data == "make_link")
async def make_link_handler(callback: types.CallbackQuery):
    me = await bot.get_me()
    user = callback.from_user
    
    if user.username:
        users[user.username.lower()] = user.id
        ref = user.username
    else:
        ref = str(user.id)

    link = f"https://t.me/{me.username}?start={ref}"
    
    await callback.message.edit_text(
        f"Ваша личная ссылка:\n{link}\n\n"
        "Отправьте её друзьям или выложите в соцсети, чтобы получать анонимные сообщения.",
        reply_markup=get_back_kb()
    )
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    st = get_user_stats(user_id)
    active_str = "Включен" if is_accepting(user_id) else "Выключен"
    blocked_count = len(blacklists.get(user_id, set()))

    text = (
        "Ваш профиль:\n\n"
        f"• Получено сообщений: {st['received']}\n"
        f"• Отправлено сообщений: {st['sent']}\n"
        f"• Прием сообщений: {active_str}\n"
        f"• В черном списке: {blocked_count}"
    )

    await callback.message.edit_text(text, reply_markup=get_back_kb())
    await callback.answer()

@dp.callback_query(F.data == "toggle_status")
async def toggle_status_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    current = is_accepting(user_id)
    settings.setdefault(user_id, {})["active"] = not current

    await callback.message.edit_reply_markup(reply_markup=get_main_kb(user_id))
    state_msg = "Прием сообщений включен" if not current else "Прием сообщений выключен"
    await callback.answer(state_msg)

@dp.callback_query(F.data == "help")
async def help_handler(callback: types.CallbackQuery):
    text = (
        "Как это работает:\n\n"
        "1. Нажмите «Создать ссылку» и скопируйте персональную ссылку.\n"
        "2. Опубликуйте её в соцсетях или отправьте знакомым.\n"
        "3. Любой человек сможет написать вам анонимно.\n"
        "4. Чтобы ответить на полученное сообщение, нажмите «Реплей 💬».\n"
        "5. Если кто-то спамит, нажмите «Заблокировать» под сообщением."
    )
    await callback.message.edit_text(text, reply_markup=get_back_kb())
    await callback.answer()

@dp.callback_query(F.data.startswith("reply:"))
async def reply_handler(callback: types.CallbackQuery):
    target_id = int(callback.data.split(":")[1])
    
    if not is_accepting(target_id):
        await callback.message.answer("Этот пользователь отключил прием анонимных сообщений.")
        await callback.answer()
        return

    if callback.from_user.id in blacklists.get(target_id, set()):
        await callback.message.answer("Вы заблокированы этим пользователем.")
        await callback.answer()
        return

    targets[callback.from_user.id] = target_id
    await callback.message.answer("Введите ответное сообщение:")
    await callback.answer()

@dp.callback_query(F.data.startswith("block:"))
async def block_handler(callback: types.CallbackQuery):
    blocked_id = int(callback.data.split(":")[1])
    blacklists.setdefault(callback.from_user.id, set()).add(blocked_id)
    
    await callback.message.answer("Пользователь заблокирован. Он больше не сможет отправлять вам сообщения.")
    await callback.answer()

@dp.message()
async def process_msg(message: types.Message):
    sender_id = message.from_user.id
    target_id = targets.get(sender_id)

    if not target_id:
        await message.answer(
            "Чтобы отправить анонимное сообщение, перейдите по ссылке нужного пользователя.",
            reply_markup=get_main_kb(sender_id)
        )
        return

    if not is_accepting(target_id):
        await message.answer("Пользователь временно отключил прием сообщений.")
        targets.pop(sender_id, None)
        return

    if sender_id in blacklists.get(target_id, set()):
        await message.answer("Вы не можете отправлять сообщения этому пользователю.")
        targets.pop(sender_id, None)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Реплей 💬", callback_data=f"reply:{sender_id}"),
            InlineKeyboardButton(text="Заблокировать", callback_data=f"block:{sender_id}")
        ]
    ])

    try:
        await bot.send_message(target_id, "Вам пришло новое анонимное сообщение:")
        await message.copy_to(chat_id=target_id, reply_markup=kb)
        
        get_user_stats(sender_id)["sent"] += 1
        get_user_stats(target_id)["received"] += 1

        targets.pop(sender_id, None)
        await message.answer("Сообщение доставлено.")
    except Exception:
        await message.answer("Не удалось доставить сообщение. Возможно, пользователь заблокировал бота.")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

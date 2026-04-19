import discord
from discord.ext import commands
import os
import sqlite3
import time as t

# ── Config ───────────────────────────────────────────────────────────────────
TOKEN         = os.environ["DISCORD_TOKEN"]
ROLE_LEVEL_10 = 1475128567397613750
ROLE_LEVEL_15 = 1475848792137011363
XP_PER_MSG    = 10
COOLDOWN_SEC  = 60
# ─────────────────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("levels.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY,
            guild_id  INTEGER,
            xp        INTEGER DEFAULT 0,
            level     INTEGER DEFAULT 0,
            last_xp   REAL    DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id, guild_id):
    conn = sqlite3.connect("levels.db")
    c = conn.cursor()
    c.execute("SELECT xp, level, last_xp FROM users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
    row = c.fetchone()
    conn.close()
    return {"xp": row[0], "level": row[1], "last_xp": row[2]} if row else {"xp": 0, "level": 0, "last_xp": 0}

def save_user(user_id, guild_id, xp, level, last_xp):
    conn = sqlite3.connect("levels.db")
    conn.execute("""
        INSERT INTO users (user_id, guild_id, xp, level, last_xp)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET xp=?, level=?, last_xp=?
    """, (user_id, guild_id, xp, level, last_xp, xp, level, last_xp))
    conn.commit()
    conn.close()

def xp_needed(level):
    return 100 * (level + 1)

# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    init_db()
    print(f"✅ Leveling bot online: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user = get_user(message.author.id, message.guild.id)
    now  = t.time()

    if now - user["last_xp"] >= COOLDOWN_SEC:
        user["xp"]      += XP_PER_MSG
        user["last_xp"]  = now

        if user["xp"] >= xp_needed(user["level"]):
            user["level"] += 1
            user["xp"]     = 0

            embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"{message.author.mention} naik ke **Level {user['level']}**!",
                color=discord.Color.green()
            )
            await message.channel.send(embed=embed)

            if user["level"] == 10:
                role = message.guild.get_role(ROLE_LEVEL_10)
                if role:
                    await message.author.add_roles(role)

            if user["level"] == 15:
                role = message.guild.get_role(ROLE_LEVEL_15)
                if role:
                    await message.author.add_roles(role)

        save_user(message.author.id, message.guild.id, user["xp"], user["level"], user["last_xp"])

    await bot.process_commands(message)

# ── Commands ──────────────────────────────────────────────────────────────────
@bot.command(name="rank")
async def rank_cmd(ctx, member: discord.Member = None):
    member = member or ctx.author
    user   = get_user(member.id, ctx.guild.id)

    embed = discord.Embed(title=f"⭐ Rank {member.display_name}", color=discord.Color.blue())
    embed.add_field(name="Level", value=str(user["level"]), inline=True)
    embed.add_field(name="XP", value=f"{user['xp']} / {xp_needed(user['level'])}", inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", aliases=["lb"])
async def lb_cmd(ctx):
    conn = sqlite3.connect("levels.db")
    rows = conn.execute("""
        SELECT user_id, level, xp FROM users
        WHERE guild_id=?
        ORDER BY level DESC, xp DESC
        LIMIT 10
    """, (ctx.guild.id,)).fetchall()
    conn.close()

    if not rows:
        await ctx.send("Belum ada data leaderboard.")
        return

    medals = ["🥇", "🥈", "🥉"]
    desc   = ""
    for i, (uid, lvl, xp) in enumerate(rows):
        medal  = medals[i] if i < 3 else f"`{i+1}.`"
        member = ctx.guild.get_member(uid)
        name   = member.display_name if member else f"User {uid}"
        desc  += f"{medal} **{name}** — Level {lvl} ({xp} XP)\n"

    embed = discord.Embed(title="🏆 Leaderboard", description=desc, color=discord.Color.gold())
    await ctx.send(embed=embed)

bot.run(TOKEN)

import discord
from discord.ext import commands
from discord import app_commands
import random, time, os

# MongoDB
from pymongo import MongoClient

#================= CONFIG =================

TOKEN = os.getenv("TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

MAIN_OWNER = 972663557420351498
OFFICIAL_SERVER_ID = 1492901903280111858  # 👈 added

EMOJI = "🪙"

WORK_CD = 1800
DAILY_CD = 86400

#================= MONGODB =================

client = MongoClient(MONGO_URI)
db = client["SamCoin"]

users_col = db["users"]
servers_col = db["servers"]
codes_col = db["codes"]
owners_col = db["owners"]
market_col = db["market"]
shop_col = db["shop"]

#================= DISCORD =================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

#================= MEMORY =================

spam = {}
msg_cd = {}
temp_owners = {}

#================= CORE FUNCTIONS =================

def get_user(uid):
    uid = str(uid)

    user = users_col.find_one({"_id": uid})

    if not user:
        user = {
            "_id": uid,
            "gcoins": 50,
            "ocoins": 0,
            "work": 0,
            "daily": 0,
            "ginv": {},
            "oinv": {},
            "premium_until": 0,
            "given_today": 0,
            "given_reset": 0
        }
        users_col.insert_one(user)

    return user


def update_user(user):
    users_col.update_one({"_id": user["_id"]}, {"$set": user})


def get_server(sid):
    sid = str(sid)

    s = servers_col.find_one({"_id": sid})

    if not s:
        s = {
            "_id": sid,
            "shop": {},
            "inv": {}
        }
        servers_col.insert_one(s)

    return s


def update_server(s):
    servers_col.update_one({"_id": s["_id"]}, {"$set": s})


def is_owner(uid):
    if uid == MAIN_OWNER:
        return True

    if uid in temp_owners:
        if time.time() < temp_owners[uid]:
            return True
        else:
            del temp_owners[uid]

    return owners_col.find_one({"_id": str(uid)}) is not None


def is_premium(u):
    return time.time() < u.get("premium_until", 0)

#================= UTIL =================

def emb(title, desc, user=None):
    e = discord.Embed(
        title=f"✨ {title}",
        description=desc,
        color=0x5865F2
    )

    if user:
        e.set_thumbnail(url=user.display_avatar.url)
        e.set_author(name=user.name, icon_url=user.display_avatar.url)

    # 💎 premium-style footer
    e.set_footer(text="SamCoin 🪙 • Premium Economy")

    # ⏱️ timestamp (good for logs + UI)
    e.timestamp = discord.utils.utcnow()

    return e
#================= READY =================

@bot.event
async def on_ready():
    await tree.sync()
    print("===================================")
    print(f"🤖 Logged in as: {bot.user}")
    print("💾 Database: MongoDB Connected")
    print("⚡ SamCoin System Ready")
    print("===================================")

#=#================= MESSAGE COIN =================

@bot.event
async def on_message(m):
    if m.author.bot:
        return

    uid = m.author.id
    now = time.time()

    # anti-spam (10 sec window, max 5 msgs)
    spam.setdefault(uid, [])
    spam[uid] = [t for t in spam[uid] if now - t < 10]
    spam[uid].append(now)

    if len(spam[uid]) > 5:
        return

    # get user (MongoDB)
    u = get_user(uid)

    # cooldown per message earn
    msg_cd.setdefault(uid, 0)

    if now - msg_cd[uid] >= 5:
        if is_premium(u):
            u["gcoins"] += 2
        else:
            u["gcoins"] += 1

        msg_cd[uid] = now
        update_user(u)

    await bot.process_commands(m)

#================= ECONOMY =================

@tree.command(name="balance")
async def balance(i: discord.Interaction, member: discord.Member = None):
    member = member or i.user

    # MongoDB user
    u = get_user(member.id)

    gcoins = u.get("gcoins", 0)
    ocoins = u.get("ocoins", 0)
    premium = is_premium(u)

    # 💎 PREMIUM UI
    if premium:
        embed = discord.Embed(
            title="💎 Premium Wallet",
            description="Exclusive benefits unlocked",
            color=0xf1c40f
        )

        embed.add_field(
            name="👤 User",
            value=member.mention,
            inline=False
        )

        embed.add_field(
            name="🪙 Global Coins",
            value=f"**{gcoins} {EMOJI}**",
            inline=True
        )

        embed.add_field(
            name="💠 Official Coins",
            value=f"**{ocoins} 💠**",
            inline=True
        )

        embed.add_field(
            name="📊 Status",
            value="💎 Premium Member",
            inline=False
        )

        embed.set_footer(text="SamCoin Premium System 💎")

    # 🟢 NORMAL USER UI
    else:
        embed = discord.Embed(
            title="💰 Wallet",
            color=0x5865F2
        )

        embed.add_field(
            name="👤 User",
            value=member.mention,
            inline=True
        )

        embed.add_field(
            name="🪙 Global Coins",
            value=f"{gcoins} {EMOJI}",
            inline=True
        )

        embed.add_field(
            name="💠 Official Coins",
            value=f"{ocoins} 💠",
            inline=True
        )

        embed.add_field(
            name="📊 Status",
            value="🟢 Active",
            inline=False
        )

        embed.set_footer(text="Upgrade to Premium for bonuses 💎")

    # common
    embed.set_thumbnail(url=member.display_avatar.url)

    await i.response.send_message(embed=embed)

#================= GIVE CONFIRM CLASS =================

class GiveConfirm(discord.ui.View):
    def __init__(self, sender, receiver, amount, currency):
        super().__init__(timeout=30)
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.currency = currency

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.sender.id:
            return await interaction.response.send_message("❌ Not your action", ephemeral=True)

        if self.sender.id == self.receiver.id:
            return await interaction.response.send_message("❌ You can't send coins to yourself", ephemeral=True)

        sender = get_user(self.sender.id)
        receiver = get_user(self.receiver.id)
        premium = is_premium(sender)

        now = time.time()

        # 🔄 reset daily limits
        if now - sender.get("given_reset", 0) >= 86400:
            sender["given_g_today"] = 0
            sender["given_o_today"] = 0
            sender["given_reset"] = now

        # ensure keys exist
        sender.setdefault("given_g_today", 0)
        sender.setdefault("given_o_today", 0)
        sender.setdefault("gcoins", 0)
        sender.setdefault("ocoins", 0)
        receiver.setdefault("gcoins", 0)
        receiver.setdefault("ocoins", 0)

        g_limit = 10000 if premium else 7500
        o_limit = 500 if premium else 0

        # ================= GCOIN =================
        if self.currency == "gcoin":

            if sender.get("gcoins", 0) < self.amount:
                return await interaction.response.send_message("❌ Not enough gcoins", ephemeral=True)

            if sender.get("given_g_today", 0) + self.amount > g_limit:
                return await interaction.response.send_message("❌ Daily gcoin limit reached", ephemeral=True)

            sender["gcoins"] -= self.amount
            receiver["gcoins"] += self.amount
            sender["given_g_today"] += self.amount

        # ================= OCOIN =================
        elif self.currency == "ocoin":

            if not is_official_server(interaction.guild.id):
                return await interaction.response.send_message(
                    "❌ Ocoins only work in official server",
                    ephemeral=True
                )

            if not premium:
                return await interaction.response.send_message(
                    "❌ Only premium users can send ocoins",
                    ephemeral=True
                )

            if sender.get("ocoins", 0) < self.amount:
                return await interaction.response.send_message("❌ Not enough ocoins", ephemeral=True)

            if sender.get("given_o_today", 0) + self.amount > o_limit:
                return await interaction.response.send_message("❌ Daily ocoin limit reached", ephemeral=True)

            sender["ocoins"] -= self.amount
            receiver["ocoins"] += self.amount
            sender["given_o_today"] += self.amount

        # 💾 SAVE
        update_user(sender)
        update_user(receiver)

        coin_emoji = "🪙" if self.currency == "gcoin" else "💠"

        embed = discord.Embed(
            title="✅ Transfer Successful",
            color=0x2ecc71
        )

        embed.add_field(name="👤 Sender", value=self.sender.mention, inline=True)
        embed.add_field(name="📥 Receiver", value=self.receiver.mention, inline=True)
        embed.add_field(
            name="💰 Amount",
            value=f"**{self.amount} {coin_emoji} ({self.currency})**",
            inline=False
        )

        if premium:
            embed.add_field(name="💎 Premium", value="Higher limits applied", inline=False)

        embed.set_footer(text="SamCoin Secure Transaction ✔")

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.sender.id:
            return await interaction.response.send_message("❌ Not your action", ephemeral=True)

        embed = discord.Embed(
            title="❌ Transfer Cancelled",
            color=0xe74c3c
        )

        embed.set_footer(text="Transaction stopped")

        await interaction.response.edit_message(embed=embed, view=None)
        
#================= GIVE =================

@tree.command(name="give")
async def give(
    i: discord.Interaction,
    member: discord.Member,
    amount: int,
    currency: str = "gcoin"
):

    if amount <= 0:
        return await i.response.send_message(
            embed=emb("Invalid Amount", "❌ Amount must be greater than 0", i.user)
        )

    if member.bot or member.id == i.user.id:
        return await i.response.send_message(
            embed=emb("Invalid Target", "❌ You can't send coins to this user", i.user)
        )

    currency = currency.lower()

    if currency not in ["gcoin", "ocoin"]:
        return await i.response.send_message(
            embed=emb("Invalid Currency", "❌ Use **gcoin** or **ocoin**", i.user)
        )

    sender = get_user(i.user.id)
    premium = is_premium(sender)

    now = time.time()

    # 🔄 RESET DAILY LIMITS
    if now - sender.get("given_reset", 0) >= 86400:
        sender["given_g_today"] = 0
        sender["given_o_today"] = 0
        sender["given_reset"] = now

    g_limit = 10000 if premium else 7500
    o_limit = 500 if premium else 0

    # 🔐 OCOIN RULES
    if currency == "ocoin":
        if not is_official_server(i.guild.id):
            return await i.response.send_message(
                embed=emb("Access Denied", "💠 Ocoins can only be used in official server", i.user)
            )

        if not premium:
            return await i.response.send_message(
                embed=emb("Premium Required", "💎 Only premium users can send ocoins", i.user)
            )

    # 💰 BALANCE CHECK
    if currency == "gcoin":
        if sender.get("gcoins", 0) < amount:
            return await i.response.send_message(
                embed=emb("Insufficient Balance", "❌ Not enough gcoins", i.user)
            )

    elif currency == "ocoin":
        if sender.get("ocoins", 0) < amount:
            return await i.response.send_message(
                embed=emb("Insufficient Balance", "❌ Not enough ocoins", i.user)
            )

    # 📊 DAILY LIMIT CHECK
    if currency == "gcoin":
        if sender.get("given_g_today", 0) + amount > g_limit:
            return await i.response.send_message(
                embed=emb(
                    "Limit Reached",
                    f"❌ Daily gcoin limit reached\nLimit: **{g_limit} 🪙**",
                    i.user
                )
            )

    elif currency == "ocoin":
        if sender.get("given_o_today", 0) + amount > o_limit:
            return await i.response.send_message(
                embed=emb(
                    "Limit Reached",
                    f"❌ Daily ocoin limit reached\nLimit: **{o_limit} 💠**",
                    i.user
                )
            )

    # 🎨 CONFIRM UI
    coin_emoji = "🪙" if currency == "gcoin" else "💠"

    embed = emb(
        "Confirm Transfer",
        f"{i.user.mention}, review your transaction below:",
        i.user
    )

    embed.add_field(name="👤 Sender", value=i.user.mention, inline=True)
    embed.add_field(name="📥 Receiver", value=member.mention, inline=True)

    embed.add_field(
        name="💰 Amount",
        value=f"**{amount} {coin_emoji} ({currency})**",
        inline=False
    )

    embed.add_field(
        name="📊 Daily Usage",
        value=(
            f"🪙 gcoin: {sender.get('given_g_today', 0)}/{g_limit}\n"
            f"💠 ocoin: {sender.get('given_o_today', 0)}/{o_limit}"
        ),
        inline=False
    )

    if premium:
        embed.add_field(
            name="💎 Premium",
            value="Higher transfer limits unlocked!",
            inline=False
        )

    embed.set_footer(text="Click confirm to complete transaction")

    await i.response.send_message(
        embed=embed,
        view=GiveConfirm(i.user, member, amount, currency)
            )
    
#================= SET / TAKE / REMOVE =================

@tree.command(name="setcoins")
async def setcoins(
    i: discord.Interaction,
    member: discord.Member,
    amount: int,
    currency: str = "gcoin"
):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    if amount < 0:
        return await i.response.send_message("❌ Invalid amount")

    currency = currency.lower()
    if currency not in ["gcoin", "ocoin"]:
        return await i.response.send_message("❌ Use gcoin or ocoin")

    u = get_user(member.id)

    if currency == "gcoin":
        u["gcoins"] = amount
        coin_emoji = "🪙"
    else:
        u["ocoins"] = amount
        coin_emoji = "💠"

    update_user(u)

    embed = discord.Embed(
        title="⚙️ Coins Updated",
        description="Balance has been set successfully",
        color=0x3498db
    )

    embed.add_field(name="👤 User", value=member.mention, inline=True)
    embed.add_field(
        name="💰 Updated",
        value=f"**{amount} {coin_emoji} ({currency})**",
        inline=True
    )

    embed.add_field(
        name="📊 Total Balance",
        value=f"🪙 {u.get('gcoins',0)} | 💠 {u.get('ocoins',0)}",
        inline=False
    )

    embed.set_footer(text="Admin Panel • SamCoin 💎")

    await i.response.send_message(embed=embed)


#================= TAKE =================

@tree.command(name="take")
async def take(
    i: discord.Interaction,
    member: discord.Member,
    amount: int,
    currency: str = "gcoin"
):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    if amount <= 0:
        return await i.response.send_message("❌ Invalid amount")

    currency = currency.lower()
    if currency not in ["gcoin", "ocoin"]:
        return await i.response.send_message("❌ Use gcoin or ocoin")

    u = get_user(member.id)

    if currency == "gcoin":
        u["gcoins"] = max(0, u.get("gcoins", 0) - amount)
        coin_emoji = "🪙"
    else:
        u["ocoins"] = max(0, u.get("ocoins", 0) - amount)
        coin_emoji = "💠"

    update_user(u)

    embed = discord.Embed(
        title="⚠️ Coins Deducted",
        description="Balance has been reduced",
        color=0xe74c3c
    )

    embed.add_field(name="👤 User", value=member.mention, inline=True)
    embed.add_field(
        name="💰 Removed",
        value=f"**{amount} {coin_emoji} ({currency})**",
        inline=True
    )

    embed.add_field(
        name="📊 New Balance",
        value=f"🪙 {u.get('gcoins',0)} | 💠 {u.get('ocoins',0)}",
        inline=False
    )

    embed.set_footer(text="Admin Panel • SamCoin 💎")

    await i.response.send_message(embed=embed)


#================= REMOVE COINS =================

@tree.command(name="removecoins")
async def removecoins(
    i: discord.Interaction,
    member: discord.Member,
    amount: int,
    currency: str = "gcoin"
):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    if amount <= 0:
        return await i.response.send_message("❌ Invalid amount")

    currency = currency.lower()
    if currency not in ["gcoin", "ocoin"]:
        return await i.response.send_message("❌ Use gcoin or ocoin")

    u = get_user(member.id)

    if currency == "gcoin":
        u["gcoins"] = max(0, u.get("gcoins", 0) - amount)
        coin_emoji = "🪙"
    else:
        u["ocoins"] = max(0, u.get("ocoins", 0) - amount)
        coin_emoji = "💠"

    update_user(u)

    embed = discord.Embed(
        title="🧹 Coins Removed",
        description="Manual balance adjustment completed",
        color=0xe67e22
    )

    embed.add_field(name="👤 User", value=member.mention, inline=True)
    embed.add_field(
        name="💰 Removed",
        value=f"**{amount} {coin_emoji} ({currency})**",
        inline=True
    )

    embed.add_field(
        name="📊 New Balance",
        value=f"🪙 {u.get('gcoins',0)} | 💠 {u.get('ocoins',0)}",
        inline=False
    )

    embed.set_footer(text="Admin Panel • SamCoin 💎")

    await i.response.send_message(embed=embed)

#================= WORK =================
@tree.command(name="work")
async def work(i: discord.Interaction):

    u = get_user(i.user.id)

    now = time.time()
    last_work = u.get("work", 0)
    remaining = WORK_CD - (now - last_work)

    premium = is_premium(u)

    # 🔒 cooldown for everyone except main owner
    if i.user.id != MAIN_OWNER and remaining > 0:
        mins = int(remaining // 60)
        secs = int(remaining % 60)

        return await i.response.send_message(
            embed=emb(
                "⏳ Work Cooldown",
                f"Try again in **{mins}m {secs}s**",
                i.user
            )
        )

    # 💰 REWARD SYSTEM
    if premium:
        g_amt = random.randint(80, 150)
        o_amt = random.randint(5, 15)
    else:
        g_amt = random.randint(25, 100)
        o_amt = random.randint(1, 5)

    # 💾 update balances
    u["gcoins"] = u.get("gcoins", 0) + g_amt
    u["ocoins"] = u.get("ocoins", 0) + o_amt
    u["work"] = now

    update_user(u)

    # 🎨 UI
    if premium:
        embed_msg = emb(
            "💼 Premium Work Complete",
            "You earned boosted rewards!",
            i.user
        )
    else:
        embed_msg = emb(
            "💼 Work Complete",
            "You earned some coins!",
            i.user
        )

    embed_msg.add_field(
        name="🪙 Gcoins Earned",
        value=f"**+{g_amt} {EMOJI}**",
        inline=True
    )

    embed_msg.add_field(
        name="💠 Ocoins Earned",
        value=f"**+{o_amt} 💠**",
        inline=True
    )

    embed_msg.add_field(
        name="📊 Total Balance",
        value=f"🪙 {u['gcoins']} | 💠 {u['ocoins']}",
        inline=False
    )

    if premium:
        embed_msg.add_field(
            name="💎 Premium Bonus",
            value="Higher rewards applied!",
            inline=False
        )

    embed_msg.set_footer(text="Come back in 30 minutes ⏳")

    await i.response.send_message(embed=embed_msg)

#================= DAILY =================

@tree.command(name="daily")
async def daily(i: discord.Interaction):

    u = get_user(i.user.id)

    now = time.time()
    remaining = DAILY_CD - (now - u.get("daily", 0))

    premium = is_premium(u)

    # 🔒 cooldown (same for everyone except main owner)
    if i.user.id != MAIN_OWNER and remaining > 0:
        hrs = int(remaining // 3600)
        mins = int((remaining % 3600) // 60)

        return await i.response.send_message(
            embed=emb(
                "Daily Cooldown",
                f"⏳ Come back in **{hrs}h {mins}m**",
                i.user
            )
        )

    # 💰 REWARD SYSTEM
    if premium:
        g_amt = random.randint(200, 400)
        o_amt = random.randint(20, 50)
    else:
        g_amt = random.randint(100, 200)
        o_amt = random.randint(5, 15)

    # 💠 OCOIN ONLY IN OFFICIAL SERVER
    if not is_official_server(i.guild.id):
        o_amt = 0

    # update balances safely
    u["gcoins"] = u.get("gcoins", 0) + g_amt
    u["ocoins"] = u.get("ocoins", 0) + o_amt
    u["daily"] = now

    update_user(u)

    # 🎨 UI
    if premium:
        embed = emb(
            "🎁 Premium Daily Reward",
            "💎 You claimed your boosted daily reward!",
            i.user
        )
    else:
        embed = emb(
            "🎁 Daily Reward Claimed",
            "Here are your daily rewards!",
            i.user
        )

    embed.add_field(name="👤 User", value=i.user.mention, inline=False)

    embed.add_field(
        name="🪙 Gcoins",
        value=f"**+{g_amt} {EMOJI}**",
        inline=True
    )

    embed.add_field(
        name="💠 Ocoins",
        value=f"**+{o_amt} 💠**",
        inline=True
    )

    embed.add_field(
        name="📊 Total Balance",
        value=f"🪙 {u.get('gcoins',0)} | 💠 {u.get('ocoins',0)}",
        inline=False
    )

    if premium:
        embed.add_field(
            name="💎 Premium Bonus",
            value="Higher rewards applied!",
            inline=False
        )

    embed.set_footer(text="Come back tomorrow for more 🎁")

    await i.response.send_message(embed=embed)
    u["daily"] = now

    update_user(u)

    # 💎 UI
    if premium:
        embed = discord.Embed(
            title="🎁 Premium Daily Reward",
            description="You claimed your boosted daily reward!",
            color=0xf1c40f
        )
    else:
        embed = discord.Embed(
            title="🎁 Daily Reward Claimed",
            color=0x2ecc71
        )

    embed.add_field(name="👤 User", value=i.user.mention, inline=False)

    embed.add_field(
        name="🪙 Gcoins",
        value=f"**+{g_amt} {EMOJI}**",
        inline=True
    )

    embed.add_field(
        name="💠 Ocoins",
        value=f"**+{o_amt} 💠**",
        inline=True
    )

    embed.add_field(
        name="📊 Total Balance",
        value=f"🪙 {u['gcoins']} | 💠 {u['ocoins']}",
        inline=False
    )

    if premium:
        embed.add_field(
            name="💎 Premium Bonus",
            value="Higher rewards applied!",
            inline=False
        )

    embed.set_footer(text="Come back tomorrow for more 🎁")

    await i.response.send_message(embed=embed)

#================= SHOP =================
@tree.command(name="buypremium")
@app_commands.describe(plan="Choose premium plan")
@app_commands.choices(plan=[
    app_commands.Choice(name="7 Days - 10,000 🪙", value="7"),
    app_commands.Choice(name="15 Days - 18,000 🪙", value="15"),
    app_commands.Choice(name="30 Days - 25,000 🪙", value="30"),
])
async def buypremium(i: discord.Interaction, plan: app_commands.Choice[str]):

    # 🔒 MUST JOIN OFFICIAL SERVER
    if not is_official_server(i.guild.id):
        embed_msg = emb(
            "Join Required",
            "💠 To buy premium, you must join the official server first!",
            i.user
        )

        embed_msg.add_field(
            name="📢 Official Server",
            value="👉 https://discord.gg/WMrzPHQCWM",
            inline=False
        )

        embed_msg.add_field(
            name="💎 Why Join?",
            value="Access premium shop, ocoins, roles & exclusive features!",
            inline=False
        )

        return await i.response.send_message(embed=embed_msg)

    u = get_user(i.user.id)

    # 🧠 plans
    plans = {
        "7": (10000, 7),
        "15": (18000, 15),
        "30": (25000, 30)
    }

    if plan.value not in plans:
        return await i.response.send_message(
            embed=emb("Error", "❌ Invalid plan selected", i.user)
        )

    price, days = plans[plan.value]

    # 💰 balance check
    if u.get("gcoins", 0) < price:
        return await i.response.send_message(
            embed=emb("Insufficient Balance", "❌ Not enough gcoins 🪙", i.user)
        )

    # 💸 deduct
    u["gcoins"] -= price

    now = time.time()
    current = u.get("premium_until", 0)

    # ⏳ extend / set
    if current > now:
        u["premium_until"] += days * 86400
    else:
        u["premium_until"] = now + (days * 86400)

    update_user(u)

    # ⏳ remaining time
    remaining = u["premium_until"] - now
    total_days = int(remaining // 86400)

    # 🎨 UI
    embed_msg = emb(
        "💎 Premium Activated!",
        "Welcome to **SamCoin Premium** 🎉",
        i.user
    )

    embed_msg.add_field(name="📦 Plan", value=f"{days} Days", inline=True)
    embed_msg.add_field(name="💰 Paid", value=f"{price} 🪙", inline=True)

    embed_msg.add_field(
        name="⏳ Total Time",
        value=f"{total_days} Days Remaining",
        inline=False
    )

    embed_msg.add_field(
        name="💎 Benefits",
        value=(
            "• Higher work rewards\n"
            "• Higher daily rewards\n"
            "• Ocoin transfers\n"
            "• Higher limits"
        ),
        inline=False
    )

    embed_msg.set_footer(text="Enjoy your premium perks 💎")

    await i.response.send_message(embed=embed_msg)
# premium status command 

@tree.command(name="premium")
async def premium(i: discord.Interaction):

    u = get_user(i.user.id)

    now = time.time()
    premium_until = u.get("premium_until", 0)
    remaining = premium_until - now

    # ❌ no premium / expired
    if remaining <= 0:
        embed_msg = emb(
            "💎 Premium Status",
            "❌ You don't have an active premium plan",
            i.user
        )

        embed_msg.add_field(
            name="💠 Upgrade",
            value="Use `/buypremium` to unlock premium benefits!",
            inline=False
        )

        return await i.response.send_message(embed=embed_msg)

    # ⏳ time calc
    days = int(remaining // 86400)
    hours = int((remaining % 86400) // 3600)

    # 💰 balances
    gcoins = u.get("gcoins", 0)
    ocoins = u.get("ocoins", 0)

    # 🎨 UI
    embed_msg = emb(
        "💎 Premium Status",
        "You are enjoying premium benefits ✨",
        i.user
    )

    embed_msg.add_field(
        name="⏳ Time Left",
        value=f"**{days}d {hours}h**",
        inline=False
    )

    embed_msg.add_field(
        name="💰 Balance",
        value=f"🪙 {gcoins} | 💠 {ocoins}",
        inline=False
    )

    embed_msg.add_field(
        name="💎 Benefits",
        value=(
            "• Higher work rewards\n"
            "• Higher daily rewards\n"
            "• Ocoin transfers\n"
            "• Higher give limits"
        ),
        inline=False
    )

    embed_msg.set_footer(text="Premium active ✔")

    await i.response.send_message(embed=embed_msg)
    
#================= OSHOP VIEW =================

@tree.command(name="oshop")
async def oshop(i: discord.Interaction):

    if not is_official_server(i.guild.id):
        return await i.response.send_message(
            embed=emb("Access Denied", "💠 OShop only available in official server", i.user)
        )

    items = list(db.oshop.find({}))

    if not items:
        return await i.response.send_message(
            embed=emb("Official Shop", "🛒 Shop is currently empty", i.user)
        )

    embed_msg = emb("🛒 Official Shop", "💠 Premium items available here", i.user)

    for item in items:
        if item["type"] == "role":
            extra = f"🪪 Role ID: {item['value']}"
        elif item["type"] == "premium":
            extra = f"💎 {item['value']} Days Premium"
        else:
            extra = f"🎒 Item: {item['value']}"

        embed_msg.add_field(
            name=f"{item['name']} ({item['type']})",
            value=(
                f"💠 Price: **{item['price']}**\n"
                f"📦 Stock: **{item.get('qty', 0)}**\n"
                f"{extra}"
            ),
            inline=False
        )

    await i.response.send_message(embed=embed_msg)


#================= ADD ITEM =================

@tree.command(name="oadditem")
@app_commands.describe(
    name="Item name",
    type="Type of item",
    price="Price in ocoins",
    value="Role ID / Days / Item name",
    quantity="Stock"
)
@app_commands.choices(type=[
    app_commands.Choice(name="Role", value="role"),
    app_commands.Choice(name="Premium", value="premium"),
    app_commands.Choice(name="Item", value="item"),
])
async def oadditem(i: discord.Interaction, name: str, type: app_commands.Choice[str], price: int, value: str, quantity: int):

    if i.user.id != MAIN_OWNER:
        return await i.response.send_message(
            embed=emb("Denied", "❌ Only main owner", i.user)
        )

    db.oshop.update_one(
        {"name": name},
        {"$set": {
            "name": name,
            "type": type.value,
            "price": price,
            "value": value,
            "qty": quantity
        }},
        upsert=True
    )

    embed_msg = emb("Item Added", f"✅ **{name}** added to oshop", i.user)
    embed_msg.add_field(name="📦 Type", value=type.value)
    embed_msg.add_field(name="💠 Price", value=f"{price}")
    embed_msg.add_field(name="📊 Stock", value=str(quantity))

    await i.response.send_message(embed=embed_msg)


#================= BUY ITEM =================

@tree.command(name="obuy")
async def obuy(i: discord.Interaction, name: str):

    if not is_official_server(i.guild.id):
        return await i.response.send_message(
            embed=emb("Access Denied", "💠 Only available in official server", i.user)
        )

    item = db.oshop.find_one({"name": name})

    if not item:
        return await i.response.send_message(
            embed=emb("Error", "❌ Item not found", i.user)
        )

    if item.get("qty", 0) <= 0:
        return await i.response.send_message(
            embed=emb("Out of Stock", "❌ Item is sold out", i.user)
        )

    u = get_user(i.user.id)

    if u.get("ocoins", 0) < item["price"]:
        return await i.response.send_message(
            embed=emb("Insufficient Balance", "❌ Not enough ocoins 💠", i.user)
        )

    # 💸 deduct
    u["ocoins"] -= item["price"]

    # 🎯 apply reward
    if item["type"] == "premium":
        days = int(item["value"])
        u["premium_until"] = max(time.time(), u.get("premium_until", 0)) + days * 86400

    elif item["type"] == "item":
        inv = u.get("inventory", {})
        inv[item["value"]] = inv.get(item["value"], 0) + 1
        u["inventory"] = inv

    elif item["type"] == "role":
        role = i.guild.get_role(int(item["value"]))
        if role:
            await i.user.add_roles(role)

    # 📉 reduce stock
    db.oshop.update_one(
        {"name": name},
        {"$inc": {"qty": -1}}
    )

    update_user(u)

    embed_msg = emb("Purchase Successful", f"✅ You bought **{name}**", i.user)
    embed_msg.add_field(name="💠 Cost", value=f"{item['price']}")
    embed_msg.add_field(name="📦 Remaining", value=str(item["qty"] - 1))

    await i.response.send_message(embed=embed_msg)


#================= REMOVE STOCK =================

@tree.command(name="oremoveitem")
async def oremoveitem(i: discord.Interaction, name: str, amount: int):

    if i.user.id != MAIN_OWNER:
        return await i.response.send_message(
            embed=emb("Denied", "❌ Only main owner", i.user)
        )

    item = db.oshop.find_one({"name": name})

    if not item:
        return await i.response.send_message(
            embed=emb("Error", "❌ Item not found", i.user)
        )

    new_qty = max(0, item.get("qty", 0) - amount)

    db.oshop.update_one(
        {"name": name},
        {"$set": {"qty": new_qty}}
    )

    await i.response.send_message(
        embed=emb("Stock Updated", f"➖ Removed {amount}\nNew stock: **{new_qty}**", i.user)
    )


#================= DELETE ITEM =================

@tree.command(name="odeleteitem")
async def odeleteitem(i: discord.Interaction, name: str):

    if i.user.id != MAIN_OWNER:
        return await i.response.send_message(
            embed=emb("Denied", "❌ Only main owner", i.user)
        )

    result = db.oshop.delete_one({"name": name})

    if result.deleted_count == 0:
        return await i.response.send_message(
            embed=emb("Error", "❌ Item not found", i.user)
        )

    await i.response.send_message(
        embed=emb("Item Deleted", f"🗑️ **{name}** removed from oshop", i.user)
    )


@tree.command(name="oinv")
async def oinv(i: discord.Interaction, member: discord.Member = None):

    member = member or i.user
    u = get_user(member.id)

    inventory = u.get("inventory", {})
    premium = is_premium(u)

    # ❌ empty inventory
    if not inventory:
        embed_msg = emb(
            "🎒 Inventory",
            f"{member.mention} has no items in inventory",
            member
        )

        if premium:
            embed_msg.title = "💎 Premium Inventory"
            embed_msg.color = 0xf1c40f

        return await i.response.send_message(embed=embed_msg)

    # 🎨 UI
    embed_msg = emb(
        "🎒 Inventory",
        f"Items owned by {member.mention}",
        member
    )

    # 💎 premium UI upgrade
    if premium:
        embed_msg.title = "💎 Premium Inventory"
        embed_msg.color = 0xf1c40f

    # 📦 show items
    for item_name, qty in inventory.items():
        embed_msg.add_field(
            name=f"📦 {item_name}",
            value=f"Quantity: **{qty}**",
            inline=False
        )

    # 💰 balances
    embed_msg.add_field(
        name="💰 Balance",
        value=f"🪙 {u.get('gcoins',0)} | 💠 {u.get('ocoins',0)}",
        inline=False
    )

    # 💎 extra premium note
    if premium:
        embed_msg.add_field(
            name="💎 Premium Bonus",
            value="You have access to exclusive items & trading perks!",
            inline=False
        )

    embed_msg.set_footer(text="SamCoin Inventory System 🎒")

    await i.response.send_message(embed=embed_msg)
#================= GSHOP (PLAYER MARKETPLACE) =================

# 📌 helper → get base price from global shop
def get_item_price(item_name):
    item = db.global_shop.find_one({"name": item_name})
    return item["price"] if item else None


#================= SELL ITEM =================

@tree.command(name="gsell")
async def gsell(i: discord.Interaction, item: str, category: str = "normal"):

    u = get_user(i.user.id)
    inv = u.get("ginv", {})

    if item not in inv or inv[item] <= 0:
        return await i.response.send_message(
            embed=emb("Error", "❌ You don't own this item", i.user)
        )

    base_price = get_item_price(item)
    if not base_price:
        return await i.response.send_message(
            embed=emb("Error", "❌ Item not in global shop", i.user)
        )

    premium = is_premium(u)

    # 🔒 category rules
    if category == "premium":
        if not premium:
            return await i.response.send_message(
                embed=emb("Denied", "💎 Premium required for this category", i.user)
            )
        price = int(base_price * 0.75)

    else:
        price = int(base_price * (0.75 if premium else 0.5))

    # ➖ remove from inventory
    inv[item] -= 1
    if inv[item] <= 0:
        del inv[item]
    u["ginv"] = inv

    # 📦 add to market
    db.gshop.insert_one({
        "item": item,
        "price": price,
        "seller": i.user.id,
        "category": category
    })

    update_user(u)

    await i.response.send_message(
        embed=emb(
            "Item Listed",
            f"📦 **{item}** listed for **{price} 🪙** in {category} market",
            i.user
        )
    )


#================= VIEW MARKET =================

@tree.command(name="gshop")
async def gshop(i: discord.Interaction):

    items = list(db.gshop.find({}))

    if not items:
        return await i.response.send_message(
            embed=emb("Market", "🛒 No listings available", i.user)
        )

    embed_msg = emb("🛒 Player Market", "Buy items from other players", i.user)

    for idx, item in enumerate(items, start=1):
        embed_msg.add_field(
            name=f"{idx}. {item['item']} ({item['category']})",
            value=f"💰 {item['price']} 🪙",
            inline=False
        )

    await i.response.send_message(embed=embed_msg)


#================= BUY FROM MARKET =================

@tree.command(name="gbuy")
async def gbuy(i: discord.Interaction, index: int):

    items = list(db.gshop.find({}))

    if index < 1 or index > len(items):
        return await i.response.send_message(
            embed=emb("Error", "❌ Invalid item index", i.user)
        )

    item = items[index - 1]

    buyer = get_user(i.user.id)
    seller = get_user(item["seller"])

    # 💰 check balance
    if buyer.get("gcoins", 0) < item["price"]:
        return await i.response.send_message(
            embed=emb("Insufficient Balance", "❌ Not enough gcoins", i.user)
        )

    # 💸 transfer
    buyer["gcoins"] -= item["price"]
    seller["gcoins"] = seller.get("gcoins", 0) + item["price"]

    # 📦 give item to buyer
    inv = buyer.get("ginv", {})
    inv[item["item"]] = inv.get(item["item"], 0) + 1
    buyer["ginv"] = inv

    # 🗑 remove listing
    db.gshop.delete_one({"_id": item["_id"]})

    update_user(buyer)
    update_user(seller)

    embed_msg = emb("Purchase Successful", f"✅ You bought **{item['item']}**", i.user)
    embed_msg.add_field(name="💰 Paid", value=f"{item['price']} 🪙")
    embed_msg.add_field(name="👤 Seller", value=f"<@{item['seller']}>")

    await i.response.send_message(embed=embed_msg)


#================= REMOVE LISTING =================

@tree.command(name="gremove")
async def gremove(i: discord.Interaction, index: int):

    items = list(db.gshop.find({}))

    if index < 1 or index > len(items):
        return await i.response.send_message(
            embed=emb("Error", "❌ Invalid index", i.user)
        )

    item = items[index - 1]

    if i.user.id != MAIN_OWNER:
        return await i.response.send_message(
            embed=emb("Denied", "❌ Only main owner", i.user)
        )

    db.gshop.delete_one({"_id": item["_id"]})

    await i.response.send_message(
        embed=emb("Removed", f"🗑 Listing removed", i.user)
    )


#================= DELETE ALL =================

@tree.command(name="gdeleteall")
async def gdeleteall(i: discord.Interaction):

    if i.user.id != MAIN_OWNER:
        return await i.response.send_message(
            embed=emb("Denied", "❌ Only main owner", i.user)
        )

    db.gshop.delete_many({})

    await i.response.send_message(
        embed=emb("Market Cleared", "🧹 All listings removed", i.user)
    )

#================= CREATE CODE =================

@tree.command(name="createcode")
@app_commands.describe(
    code="Code name",
    reward="Reward type",
    value="Item name / role ID / premium days / none",
    amount="Amount (for coins)",
    uses="Number of uses",
    scope="global or official"
)
@app_commands.choices(
    reward=[
        app_commands.Choice(name="Gcoins", value="gcoin"),
        app_commands.Choice(name="Ocoins", value="ocoin"),
        app_commands.Choice(name="Item", value="item"),
        app_commands.Choice(name="Role", value="role"),
        app_commands.Choice(name="Premium", value="premium"),
    ],
    scope=[
        app_commands.Choice(name="Global (All Servers)", value="global"),
        app_commands.Choice(name="Official Server Only", value="official"),
    ]
)
async def createcode(
    i: discord.Interaction,
    code: str,
    reward: app_commands.Choice[str],
    value: str = "none",
    amount: int = 0,
    uses: int = 1,
    scope: app_commands.Choice[str] = None
):

    if i.user.id != MAIN_OWNER:
        return await i.response.send_message(
            embed=emb("Denied", "❌ Only main owner can create codes", i.user)
        )

    scope_value = scope.value if scope else "global"

    db.codes.insert_one({
        "code": code.lower(),
        "reward": reward.value,
        "value": value,
        "amount": amount,
        "uses": uses,
        "scope": scope_value,
        "redeemed_by": []   # 🔥 NEW
    })

    embed_msg = emb("Code Created", f"🎁 Code **{code}** created", i.user)
    embed_msg.add_field(name="🎯 Type", value=reward.value, inline=True)
    embed_msg.add_field(name="🌍 Scope", value=scope_value, inline=True)
    embed_msg.add_field(name="🔁 Uses", value=str(uses), inline=True)

    await i.response.send_message(embed=embed_msg)


#================= REDEEM =================

@tree.command(name="redeem")
async def redeem(i: discord.Interaction, code: str):

    code_data = db.codes.find_one({"code": code.lower()})

    if not code_data:
        return await i.response.send_message(
            embed=emb("Error", "❌ Invalid or expired code", i.user)
        )

    # 🔒 one user one redeem
    if i.user.id in code_data.get("redeemed_by", []):
        return await i.response.send_message(
            embed=emb("Already Used", "❌ You already redeemed this code", i.user)
        )

    # 🔒 official server restriction
    if code_data.get("scope") == "official":
        if not is_official_server(i.guild.id):
            return await i.response.send_message(
                embed=emb(
                    "Access Denied",
                    "💠 This code can only be used in the official server",
                    i.user
                )
            )

    u = get_user(i.user.id)
    reward = code_data["reward"]

    #================= APPLY REWARD =================

    if reward == "gcoin":
        u["gcoins"] = u.get("gcoins", 0) + code_data["amount"]

    elif reward == "ocoin":
        u["ocoins"] = u.get("ocoins", 0) + code_data["amount"]

    elif reward == "item":
        inv = u.get("inventory", {})
        inv[code_data["value"]] = inv.get(code_data["value"], 0) + 1
        u["inventory"] = inv

    elif reward == "premium":
        days = int(code_data["value"])
        u["premium_until"] = max(time.time(), u.get("premium_until", 0)) + days * 86400

    elif reward == "role":
        role = i.guild.get_role(int(code_data["value"]))
        if role:
            await i.user.add_roles(role)

    #================= UPDATE CODE =================

    if code_data["uses"] <= 1:
        db.codes.delete_one({"_id": code_data["_id"]})
    else:
        db.codes.update_one(
            {"_id": code_data["_id"]},
            {
                "$inc": {"uses": -1},
                "$push": {"redeemed_by": i.user.id}  # 🔥 SAVE USER
            }
        )

    update_user(u)

    #================= UI =================

    embed_msg = emb("Redeemed Successfully", f"🎉 Code **{code}** applied!", i.user)

    if reward == "gcoin":
        embed_msg.add_field(name="Reward", value=f"{code_data['amount']} 🪙", inline=False)

    elif reward == "ocoin":
        embed_msg.add_field(name="Reward", value=f"{code_data['amount']} 💠", inline=False)

    elif reward == "premium":
        embed_msg.add_field(name="Reward", value=f"{code_data['value']} Days 💎", inline=False)

    elif reward == "item":
        embed_msg.add_field(name="Reward", value=f"🎒 {code_data['value']}", inline=False)

    elif reward == "role":
        embed_msg.add_field(name="Reward", value="🪪 Role Granted", inline=False)

    embed_msg.set_footer(text="SamCoin Code System 🎁")

    await i.response.send_message(embed=embed_msg)

#================= OWNER =================

@tree.command(name="addowner")
async def addowner(i: discord.Interaction, member: discord.Member):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    o = load(OWNERS_FILE)
    o[str(member.id)] = True
    save(OWNERS_FILE, o)

    await i.response.send_message("✅ Owner added")
    
@tree.command(name="removeowner")
async def removeowner(i: discord.Interaction, member: discord.Member):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    o = load(OWNERS_FILE)
    o.pop(str(member.id), None)
    save(OWNERS_FILE, o)

    await i.response.send_message("✅ Owner removed")
    
@tree.command(name="owners")
async def owners(i: discord.Interaction):
    o = load(OWNERS_FILE)

    msg = f"👑 Main Owner: <@{MAIN_OWNER}>\n\n"

    if o:
        msg += "🛡️ Other Owners:\n"
        for uid in o:
            msg += f"<@{uid}>\n"
    else:
        msg += "No extra owners"

    await i.response.send_message(msg)

#================= LOTTERY =================

@tree.command(name="lottery")
async def lottery(i: discord.Interaction):
    d = data()
    u = user(d, i.user.id)

    # entry fee
    if u["coins"] < 10:
        return await i.response.send_message("❌ You need 10 🪙 to play")

    u["coins"] -= 10

    if random.choice([True, False]):
        w = random.randint(50, 200)
        u["coins"] += w
        msg = f"🎉 You won {w} 🪙!"
    else:
        msg = "❌ You lost 10 🪙"

    save(DATA_FILE, d)
    await i.response.send_message(msg)

#================= LEADERBOARD =================

@tree.command(name="top")
async def top(i: discord.Interaction):
    d = data()["users"]
    sorted_users = sorted(d.items(), key=lambda x: x[1]["coins"], reverse=True)[:10]

    msg = ""
    for idx, (uid, val) in enumerate(sorted_users):
        try:
            user_obj = await bot.fetch_user(int(uid))
            name = user_obj.name
        except:
            name = uid

        msg += f"{idx+1}. {name} - {val['coins']}\n"

    await i.response.send_message(msg or "Empty")
    
@tree.command(name="globaltop")
async def globaltop(i: discord.Interaction):
    d = data()["users"]
    sorted_users = sorted(d.items(), key=lambda x: x[1]["coins"], reverse=True)[:10]

    embed = discord.Embed(
        title="🌍 Global Leaderboard",
        color=0x5865F2
    )

    if not sorted_users:
        embed.description = "No data available"
    else:
        for idx, (uid, val) in enumerate(sorted_users):
            try:
                user_obj = await bot.fetch_user(int(uid))
                name = user_obj.name
            except:
                name = uid

            embed.add_field(
                name=f"#{idx+1} {name}",
                value=f"{val['coins']} 🪙",
                inline=False
            )

    await i.response.send_message(embed=embed)

#================= RESET =================

@tree.command(name="resetserver")
async def resetserver(i: discord.Interaction):
    if not is_owner(i.user.id):
        return await i.response.send_message("❌ No permission")

    d = data()
    sid = str(i.guild.id)

    if sid in d["servers"]:
        d["servers"][sid] = {"shop": {}, "inv": {}}
        save(DATA_FILE, d)

    await i.response.send_message("✅ Server data reset")
    
@tree.command(name="resetglobal")
async def resetglobal(i: discord.Interaction):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    d = data()
    d["users"] = {}
    d["global_shop"] = {}
    save(DATA_FILE, d)

    await i.response.send_message("✅ Global data reset")
    
#================= TEMP OWNER =================

@tree.command(name="tempowner")
async def tempowner(i: discord.Interaction, member: discord.Member, minutes: int):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    expire = time.time() + (minutes * 60)
    temp_owners[member.id] = expire

    await i.response.send_message(f"✅ {member.name} is owner for {minutes} minutes")
    
#================= HELP =================

@tree.command(name="help")
async def help_cmd(i: discord.Interaction):
    embed = discord.Embed(
        title="📖 Help Menu",
        color=0x5865F2
    )

    embed.add_field(
        name="💰 Economy",
        value="""
/balance - Check coins  
/give - Send coins  
/work - Earn coins  
/daily - Daily reward  
/lottery - Try luck  
""",
        inline=False
    )

    embed.add_field(
        name="🛒 Shop",
        value="""
/shop - View shop  
/buy - Buy item  
/inventory - Your items  
""",
        inline=False
    )

    embed.add_field(
        name="🌍 Global",
        value="""
/globalshop - Global shop  
/buyglobal - Buy global item  
/globalinventory - Your global items  
""",
        inline=False
    )

    embed.add_field(
        name="🎁 Redeem",
        value="""
/redeem - Redeem code  
""",
        inline=False
    )

    embed.add_field(
        name="💎 Premium",
        value="""
/buypremium - Buy premium  
/premium - Check premium time  
""",
        inline=False
    )

    embed.add_field(
        name="📊 Other",
        value="""
/top - Leaderboard  
/globaltop - Global leaderboard  
""",
        inline=False
    )

    embed.set_footer(text="Use /ownerhelp for admin commands 👑")

    await i.response.send_message(embed=embed)

@tree.command(name="ownerhelp")
async def ownerhelp(i: discord.Interaction):
    if not is_owner(i.user.id):
        return await i.response.send_message("❌ No permission")

    embed = discord.Embed(
        title="👑 Owner Commands",
        color=0xe74c3c
    )

    embed.add_field(
        name="💰 Economy Control",
        value="""
/give (bypass)
/take
/setcoins
""",
        inline=False
    )

    embed.add_field(
        name="🛒 Shop Control",
        value="""
/additem
""",
        inline=False
    )

    embed.add_field(
        name="🌍 Global Control",
        value="""
/addglobalitem
/resetglobal
""",
        inline=False
    )

    embed.add_field(
        name="🎁 Codes",
        value="""
/createcode
""",
        inline=False
    )

    embed.add_field(
        name="👑 Owner Management",
        value="""
/addowner
/removeowner
/tempowner
""",
        inline=False
    )

    embed.add_field(
        name="⚙️ Server",
        value="""
/resetserver
""",
        inline=False
    )

    await i.response.send_message(embed=embed)
#================= RUN =================

bot.run(TOKEN)

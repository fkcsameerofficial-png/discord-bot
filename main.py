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
    remaining = WORK_CD - (now - u.get("work", 0))

    premium = is_premium(u)

    # 🔒 cooldown (same for everyone except main owner)
    if i.user.id != MAIN_OWNER and remaining > 0:
        mins = int(remaining // 60)
        secs = int(remaining % 60)

        return await i.response.send_message(
            embed=emb(
                "Work Cooldown",
                f"⏳ Try again in **{mins}m {secs}s**",
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

    # 💠 OCOIN ONLY IN OFFICIAL SERVER
    if not is_official_server(i.guild.id):
        o_amt = 0

    # update balances safely
    u["gcoins"] = u.get("gcoins", 0) + g_amt
    u["ocoins"] = u.get("ocoins", 0) + o_amt
    u["work"] = now

    update_user(u)

    # 🎨 UI (premium style)
    if premium:
        embed = emb(
            "💼 Premium Work Complete",
            "💎 You earned boosted rewards!",
            i.user
        )
    else:
        embed = emb(
            "💼 Work Complete",
            "You earned some coins!",
            i.user
        )

    embed.add_field(name="👤 User", value=i.user.mention, inline=False)

    embed.add_field(
        name="🪙 Gcoins Earned",
        value=f"**+{g_amt} {EMOJI}**",
        inline=True
    )

    embed.add_field(
        name="💠 Ocoins Earned",
        value=f"**+{o_amt} 💠**",
        inline=True
    )

    embed.add_field(
        name="📊 New Balance",
        value=f"🪙 {u.get('gcoins',0)} | 💠 {u.get('ocoins',0)}",
        inline=False
    )

    if premium:
        embed.add_field(
            name="💎 Premium Bonus",
            value="Higher rewards applied!",
            inline=False
        )

    embed.set_footer(text="Come back later for more work 💼")

    await i.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="💼 Work Complete",
            color=0x2ecc71
        )

    embed.add_field(name="👤 User", value=i.user.mention, inline=False)

    embed.add_field(
        name="🪙 Gcoins Earned",
        value=f"**+{g_amt} {EMOJI}**",
        inline=True
    )

    embed.add_field(
        name="💠 Ocoins Earned",
        value=f"**+{o_amt} 💠**",
        inline=True
    )

    embed.add_field(
        name="📊 New Balance",
        value=f"🪙 {u['gcoins']} | 💠 {u['ocoins']}",
        inline=False
    )

    if premium:
        embed.add_field(
            name="💎 Premium Bonus",
            value="Higher rewards applied!",
            inline=False
        )

    embed.set_footer(text="Come back later for more work 💼")

    await i.response.send_message(embed=embed)

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

    u = get_user(i.user.id)

    plans = {
        "7": (10000, 7),
        "15": (18000, 15),
        "30": (25000, 30)
    }

    price, days = plans[plan.value]

    if u.get("gcoins", 0) < price:
        return await i.response.send_message(
            embed=emb("Insufficient Balance", "❌ Not enough gcoins", i.user)
        )

    u["gcoins"] -= price

    now = time.time()
    current = u.get("premium_until", 0)

    if current > now:
        u["premium_until"] += days * 86400
    else:
        u["premium_until"] = now + (days * 86400)

    update_user(u)

    embed = emb(
        "💎 Premium Activated!",
        f"Enjoy your benefits for **{days} days**",
        i.user
    )

    embed.add_field(name="📦 Plan", value=f"{days} Days", inline=True)
    embed.add_field(name="💰 Paid", value=f"{price} 🪙", inline=True)

    await i.response.send_message(embed=embed)
# premium status command 

@tree.command(name="premium")
async def premium(i: discord.Interaction):

    u = get_user(i.user.id)

    remaining = u.get("premium_until", 0) - time.time()

    if remaining <= 0:
        return await i.response.send_message(
            embed=emb("Premium Status", "❌ You don't have premium", i.user)
        )

    days = int(remaining // 86400)
    hours = int((remaining % 86400) // 3600)

    embed = emb(
        "💎 Premium Status",
        f"You are a premium user!",
        i.user
    )

    embed.add_field(name="⏳ Time Left", value=f"{days}d {hours}h", inline=False)

    await i.response.send_message(embed=embed)
    
@tree.command(name="additem")
async def additem(i: discord.Interaction, name: str, price: int, quantity: int):
    if not is_owner(i.user.id):
        return await i.response.send_message("❌ No permission")

    d = data()
    server_data = server(d, i.guild.id)

    server_data["shop"][name] = {
        "price": price,
        "qty": quantity
    }

    save(DATA_FILE, d)

    embed = discord.Embed(
        title="✅ Item Added",
        color=0x2ecc71
    )

    embed.add_field(name="📦 Item", value=name, inline=True)
    embed.add_field(name="💰 Price", value=f"{price} 🪙", inline=True)
    embed.add_field(name="📊 Quantity", value=str(quantity), inline=True)

    await i.response.send_message(embed=embed)
    
@tree.command(name="shop")
async def shop(i: discord.Interaction):
    d = data()
    s = server(d, i.guild.id)

    embed = discord.Embed(title="🛒 Shop", color=0x3498db)

    if not s["shop"]:
        embed.description = "Empty shop"
    else:
        for name, val in s["shop"].items():
            embed.add_field(
                name=name,
                value=f"💰 {val['price']} 🪙 | 📦 {val['qty']} left",
                inline=False
            )

    await i.response.send_message(embed=embed)

@tree.command(name="buy")
async def buy(i: discord.Interaction, item: str):
    d = data()
    s = server(d, i.guild.id)
    u = user(d, i.user.id)

    if item not in s["shop"]:
        return await i.response.send_message("❌ Not found")

    item_data = s["shop"][item]

    if item_data["qty"] <= 0:
        return await i.response.send_message("❌ Out of stock")

    if not is_owner(i.user.id):
        if u["coins"] < item_data["price"]:
            return await i.response.send_message("❌ Not enough")
        u["coins"] -= item_data["price"]

    item_data["qty"] -= 1

    s["inv"].setdefault(str(i.user.id), {})
    inv = s["inv"][str(i.user.id)]
    inv[item] = inv.get(item, 0) + 1

    save(DATA_FILE, d)

    embed = discord.Embed(
        title="🛒 Purchase Successful",
        color=0x2ecc71
    )
    embed.add_field(name="📦 Item", value=item, inline=True)
    embed.add_field(name="💰 Price", value=f"{item_data['price']} 🪙", inline=True)
    embed.add_field(name="📊 Remaining", value=str(item_data["qty"]), inline=True)

    await i.response.send_message(embed=embed)


@tree.command(name="inventory")
async def inventory(i: discord.Interaction):
    d = data()
    inv = server(d, i.guild.id)["inv"].get(str(i.user.id), {})

    if not inv:
        return await i.response.send_message("📦 Your inventory is empty")

    embed = discord.Embed(
        title="🎒 Your Inventory",
        color=0x5865F2
    )

    for item, qty in inv.items():
        embed.add_field(name=item, value=f"x{qty}", inline=True)

    await i.response.send_message(embed=embed)

#================= GLOBAL SHOP =================

@tree.command(name="addglobalitem")
async def addglobalitem(i: discord.Interaction, name: str, price: int):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    d = data()
    d["global_shop"][name] = price
    save(DATA_FILE, d)

    await i.response.send_message("✅ Added")

@tree.command(name="globalshop")
async def globalshop(i):
    d = data()
    msg = "\n".join([f"{k} - {v}" for k, v in d["global_shop"].items()])
    await i.response.send_message(msg or "Empty")

@tree.command(name="buyglobal")
async def buyglobal(i: discord.Interaction, item: str):
    d = data()
    u = user(d, i.user.id)

    if item not in d["global_shop"]:
        return await i.response.send_message("❌ Not found")

    price = d["global_shop"][item]

    if not is_owner(i.user.id):
        if u["coins"] < price:
            return await i.response.send_message("❌ Not enough")
        u["coins"] -= price

    u["ginv"][item] = u["ginv"].get(item, 0) + 1
    save(DATA_FILE, d)

    await i.response.send_message("✅ Bought")
    
@tree.command(name="globalinventory")
async def globalinventory(i):
    d = data()
    inv = user(d, i.user.id)["ginv"]
    msg = "\n".join([f"{k} x{v}" for k, v in inv.items()])
    await i.response.send_message(msg or "Empty")

#================= REDEEM =================

@tree.command(name="createcode")
async def createcode(i: discord.Interaction, code: str, amount: int):
    if not is_owner(i.user.id):
        return await i.response.send_message("❌ No permission")

    c = load(CODES_FILE)
    c[code] = amount
    save(CODES_FILE, c)

    await i.response.send_message("✅ Code created")

@tree.command(name="redeem")
async def redeem(i: discord.Interaction, code: str):
    c = load(CODES_FILE)
    d = data()

    if code not in c:
        return await i.response.send_message("❌ Invalid code")

    user(d, i.user.id)["coins"] += c[code]
    del c[code]

    save(CODES_FILE, c)
    save(DATA_FILE, d)

    await i.response.send_message("✅ Redeemed")

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

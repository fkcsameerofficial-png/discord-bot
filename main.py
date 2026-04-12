import discord
from discord.ext import commands, tasks
from discord import app_commands
import json, random, time, os

TOKEN = os.getenv("TOKEN")
MAIN_OWNER = 972663557420351498
EMOJI = "🪙"

WORK_CD = 1800
DAILY_CD = 86400

DATA_FILE = "data.json"
CODES_FILE = "codes.json"
OWNERS_FILE = "owners.json"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

spam = {}
msg_cd = {}
temp_owners = {}

# ================= UTIL =================
def emb(t, d):
    e = discord.Embed(
        title=f"✨ {t}",
        description=d,
        color=0x5865F2
    )
    e.set_footer(text="SamCoin 💰")
    return e

def load(f):
    try:
        with open(f) as x:
            return json.load(x)
    except:
        return {}

def save(f, d):
    with open(f, "w") as x:
        json.dump(d, x, indent=4)

def data():
    d = load(DATA_FILE)
    d.setdefault("users", {})
    d.setdefault("servers", {})
    d.setdefault("global_shop", {})
    return d

def user(d, uid):
    uid = str(uid)
    if uid not in d["users"]:
        d["users"][uid] = {"coins":50,"work":0,"daily":0,"ginv":{}}
    return d["users"][uid]

def server(d, sid):
    sid = str(sid)
    if sid not in d["servers"]:
        d["servers"][sid] = {"shop":{}, "inv":{}}
    return d["servers"][sid]

def is_owner(uid):
    return uid == MAIN_OWNER or str(uid) in load(OWNERS_FILE) or uid in temp_owners

# ================= READY =================
@bot.event
async def on_ready():
    await tree.sync()
    print("✅ Bot Ready")

# ================= MESSAGE COIN =================
@bot.event
async def on_message(m):
    if m.author.bot:
        return

    uid = m.author.id
    now = time.time()

    spam.setdefault(uid, [])
    spam[uid] = [t for t in spam[uid] if now - t < 10]
    spam[uid].append(now)
    if len(spam[uid]) > 5:
        return

    d = data()
    u = user(d, uid)

    msg_cd.setdefault(uid, 0)
    if now - msg_cd[uid] >= 5:
        u["coins"] += 1
        msg_cd[uid] = now
        save(DATA_FILE, d)

# ================= ECONOMY =================
@tree.command(name="balance")
async def balance(i: discord.Interaction, member: discord.Member = None):
    member = member or i.user
    d = data()
    await i.response.send_message(embed=emb("Balance", f"{member.name}: {user(d, member.id)['coins']} {EMOJI}"))

class GiveConfirm(discord.ui.View):
    def __init__(self, sender, receiver, amount):
        super().__init__(timeout=30)
        self.sender = sender
        self.receiver = receiver
        self.amount = amount

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.sender:
            return await interaction.response.send_message("❌ Not your action", ephemeral=True)

        d = data()
        s = user(d, self.sender.id)
        r = user(d, self.receiver.id)

        if not is_owner(self.sender.id):
            if s["coins"] < self.amount:
                return await interaction.response.send_message("❌ Not enough coins", ephemeral=True)
            s["coins"] -= self.amount

        r["coins"] += self.amount
        save(DATA_FILE, d)

        embed = discord.Embed(
            title="💸 Transaction Done",
            description=f"{self.sender.mention} ➜ {self.receiver.mention}\n**{self.amount} {EMOJI} sent**",
            color=0x2ecc71
        )

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.sender:
            return await interaction.response.send_message("❌ Not your action", ephemeral=True)

        await interaction.response.edit_message(content="❌ Cancelled", view=None)


@tree.command(name="give")
async def give(i: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        return await i.response.send_message("❌ Invalid amount")

    embed = discord.Embed(
        title="⚠️ Confirm Transfer",
        description=f"Send **{amount} {EMOJI}** to {member.mention}?",
        color=0xf1c40f
    )

    await i.response.send_message(embed=embed, view=GiveConfirm(i.user, member, amount))

@tree.command(name="take")
async def take(i: discord.Interaction, member: discord.Member, amount: int):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    d = data()
    u = user(d, member.id)

    u["coins"] = max(0, u["coins"] - amount)
    save(DATA_FILE, d)

    await i.response.send_message(f"✅ Took {amount} {EMOJI} from {member.mention}")

@tree.command(name="setcoins")
async def setcoins(i: discord.Interaction, member: discord.Member, amount: int):
    if not is_owner(i.user.id):
        return await i.response.send_message("❌ No permission")

    d = data()
    user(d, member.id)["coins"] = amount
    save(DATA_FILE, d)
    await i.response.send_message("✅ Set")

@tree.command(name="work")
async def work(i: discord.Interaction):
    d = data()
    u = user(d, i.user.id)

    if i.user.id != MAIN_OWNER and time.time() - u["work"] < WORK_CD:
        return await i.response.send_message("⏳ Wait before working again")

    amt = random.randint(25, 100)
    u["coins"] += amt
    u["work"] = time.time()
    save(DATA_FILE, d)
    await i.response.send_message(f"💰 You earned {amt}")

@tree.command(name="daily")
async def daily(i: discord.Interaction):
    d = data()
    u = user(d, i.user.id)

    if i.user.id != MAIN_OWNER and time.time() - u["daily"] < DAILY_CD:
        return await i.response.send_message("⏳ Already claimed")

    amt = random.randint(25, 50)
    u["coins"] += amt
    u["daily"] = time.time()
    save(DATA_FILE, d)
    await i.response.send_message(f"🎁 You got {amt}")

# ================= SHOP =================
@tree.command(name="additem")
async def additem(i, name: str, price: int, quantity: int):
    if not is_owner(i.user.id):
        return await i.response.send_message("❌ No permission")

    d = data()
    server(d, i.guild.id)["shop"][name] = {"price": price, "qty": quantity}
    save(DATA_FILE, d)

    await i.response.send_message("✅ Item added")

@tree.command(name="shop")
async def shop(i):
    d = data()
    s = server(d, i.guild.id)

    embed = discord.Embed(title="🛒 Shop", color=0x3498db)

    if not s["shop"]:
        embed.description = "Empty shop"
    else:
        for name, val in s["shop"].items():
            embed.add_field(
                name=name,
                value=f"💰 {val['price']} | 📦 {val['qty']} left",
                inline=False
            )

    await i.response.send_message(embed=embed)

@tree.command(name="buy")
async def buy(i, item: str):
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
    await i.response.send_message("✅ Bought")

@tree.command(name="inventory")
async def inventory(i):
    d = data()
    inv = server(d, i.guild.id)["inv"].get(str(i.user.id), {})
    msg = "\n".join([f"{k} x{v}" for k, v in inv.items()])
    await i.response.send_message(msg or "Empty")

# ================= GLOBAL SHOP =================
@tree.command(name="addglobalitem")
async def addglobalitem(i, name: str, price: int):
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
async def buyglobal(i, item: str):
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

# ================= REDEEM =================
@tree.command(name="createcode")
async def createcode(i, code: str, amount: int):
    if not is_owner(i.user.id):
        return await i.response.send_message("❌ No permission")

    c = load(CODES_FILE)
    c[code] = amount
    save(CODES_FILE, c)
    await i.response.send_message("✅ Code created")

@tree.command(name="redeem")
async def redeem(i, code: str):
    c = load(CODES_FILE)
    d = data()

    if code not in c:
        return await i.response.send_message("❌ Invalid code")

    user(d, i.user.id)["coins"] += c[code]
    del c[code]
    save(CODES_FILE, c)
    save(DATA_FILE, d)

    await i.response.send_message("✅ Redeemed")

# ================= OWNER =================
@tree.command(name="addowner")
async def addowner(i, member: discord.Member):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    o = load(OWNERS_FILE)
    o[str(member.id)] = True
    save(OWNERS_FILE, o)
    await i.response.send_message("✅ Owner added")

@tree.command(name="removeowner")
async def removeowner(i, member: discord.Member):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    o = load(OWNERS_FILE)
    o.pop(str(member.id), None)
    save(OWNERS_FILE, o)
    await i.response.send_message("✅ Owner removed")

# ✅ FIXED OWNERS
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

# ================= LOTTERY =================
@tree.command(name="lottery")
async def lottery(i):
    d = data()
    u = user(d, i.user.id)

    if random.choice([True, False]):
        w = random.randint(50, 200)
        u["coins"] += w
        msg = f"🎉 Won {w}"
    else:
        msg = "❌ Lost"

    save(DATA_FILE, d)
    await i.response.send_message(msg)

# ================= LEADERBOARD =================
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
    await top(i)

# ================= RESET =================
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

# ================= TEMP OWNER =================
@tree.command(name="tempowner")
async def tempowner(i: discord.Interaction, member: discord.Member, minutes: int):
    if i.user.id != MAIN_OWNER:
        return await i.response.send_message("❌ Only main owner")

    expire = time.time() + (minutes * 60)
    temp_owners[member.id] = expire

    await i.response.send_message(f"✅ {member.name} is owner for {minutes} minutes")

# ================= HELP =================
@tree.command(name="help")
async def help_cmd(i: discord.Interaction):
    await i.response.send_message("""
💰 Economy:
/balance /give /work /daily

🛒 Shop:
/shop /buy /inventory

🌍 Global:
/globalshop /buyglobal /globalinventory

🎁 Redeem:
/redeem

📊 Other:
/top /lottery
""")

@tree.command(name="ownerhelp")
async def ownerhelp(i: discord.Interaction):
    if not is_owner(i.user.id):
        return await i.response.send_message("❌ No permission")

    await i.response.send_message("""
👑 Owner Commands:
/give (bypass)
/take
/setcoins
/additem
/addglobalitem
/createcode
/addowner
/removeowner
/tempowner
/resetserver
/resetglobal
""")

# ================= RUN =================
bot.run(TOKEN)

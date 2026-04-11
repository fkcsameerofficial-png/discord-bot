import discord
from discord.ext import commands
import json, random, time, os

TOKEN = os.getenv("TOKEN")

MAIN_OWNER = 972663557420351498

COIN_NAME = "SamCoin"
EMOJI = "🪙"

WORK_CD = 1800
DAILY_CD = 86400

DATA_FILE = "data.json"
CODES_FILE = "codes.json"
OWNERS_FILE = "owners.json"

# ================= MEMORY =================
spam_tracker = {}
msg_cooldown = {}
temp_owners = {}

# ================= BASIC =================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def load(file):
    try:
        with open(file) as f:
            return json.load(f)
    except:
        return {}

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def get_data():
    data = load(DATA_FILE)
    if "users" not in data:
        data["users"] = {}
    if "global_shop" not in data:
        data["global_shop"] = {}
    if "servers" not in data:
        data["servers"] = {}
    return data

def get_user(data, uid):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"coins":50,"work":0,"daily":0,"ginv":{}}
    return data["users"][uid]

def get_server(data, sid):
    sid = str(sid)
    if sid not in data["servers"]:
        data["servers"][sid] = {"shop":{},"inv":{}}
    return data["servers"][sid]

def is_main_owner(uid):
    return uid == MAIN_OWNER

def is_owner(ctx):
    owners = load(OWNERS_FILE)
    return (
        ctx.author.id == MAIN_OWNER
        or str(ctx.author.id) in owners
        or ctx.author.id in temp_owners
    )

# ================= READY =================

@bot.event
async def on_ready():
    print(f"Online as {bot.user}")

# ================= MESSAGE SYSTEM =================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    now = time.time()

    # 👑 MAIN OWNER BYPASS
    if is_main_owner(uid):
        data = get_data()
        user = get_user(data, uid)
        user["coins"] += 1
        save(DATA_FILE, data)
        await bot.process_commands(message)
        return

    # 🚨 spam protection
    spam_tracker.setdefault(uid, [])
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < 10]
    spam_tracker[uid].append(now)

    if len(spam_tracker[uid]) > 5:
        return

    # 💰 message coin (5 sec cooldown)
    data = get_data()
    user = get_user(data, uid)

    msg_cooldown.setdefault(uid, 0)

    if now - msg_cooldown[uid] >= 5:
        user["coins"] += 1
        msg_cooldown[uid] = now
        save(DATA_FILE, data)

    await bot.process_commands(message)

# ================= ECONOMY =================

@bot.command()
async def balance(ctx, member: discord.Member=None):
    data = get_data()
    member = member or ctx.author
    user = get_user(data, member.id)
    await ctx.send(f"{member.name}: {user['coins']} {EMOJI}")

@bot.command()
async def work(ctx):
    data = get_data()
    user = get_user(data, ctx.author.id)

    if not is_main_owner(ctx.author.id):
        if time.time() - user["work"] < WORK_CD:
            return await ctx.send("Wait 30 min")

    amt = random.randint(25,100)
    user["coins"] += amt
    user["work"] = time.time()
    save(DATA_FILE,data)

    await ctx.send(f"You earned {amt} {EMOJI}")

@bot.command()
async def daily(ctx):
    data = get_data()
    user = get_user(data, ctx.author.id)

    if not is_main_owner(ctx.author.id):
        if time.time() - user["daily"] < DAILY_CD:
            return await ctx.send("Already claimed")

    amt = random.randint(25,50)
    user["coins"] += amt
    user["daily"] = time.time()
    save(DATA_FILE,data)

    await ctx.send(f"You got {amt} {EMOJI}")

# ================= GIVE / TAKE =================

@bot.command()
async def give(ctx, member: discord.Member, amount:int):
    data = get_data()
    s = get_user(data, ctx.author.id)
    r = get_user(data, member.id)

    if amount > s["coins"]:
        return await ctx.send("Not enough")

    s["coins"] -= amount
    r["coins"] += amount
    save(DATA_FILE,data)

    await ctx.send(f"Sent {amount} {EMOJI}")

@bot.command()
async def take(ctx, member: discord.Member, amount:int):
    if not is_owner(ctx):
        return

    data = get_data()
    user = get_user(data, member.id)

    user["coins"] = max(0, user["coins"] - amount)
    save(DATA_FILE,data)

    await ctx.send(f"Taken {amount} {EMOJI}")

# ================= GLOBAL SHOP =================

@bot.command()
async def addglobalitem(ctx, name, price:int):
    if not is_owner(ctx):
        return
    data = get_data()
    data["global_shop"][name] = price
    save(DATA_FILE,data)
    await ctx.send("Added")

@bot.command()
async def globalshop(ctx):
    data = get_data()
    shop = data["global_shop"]
    msg = "\n".join([f"{k}-{v}" for k,v in shop.items()])
    await ctx.send(msg or "Empty")

@bot.command()
async def buyglobal(ctx, item):
    data = get_data()
    user = get_user(data, ctx.author.id)

    if item not in data["global_shop"]:
        return await ctx.send("Not found")

    price = data["global_shop"][item]
    if user["coins"] < price:
        return await ctx.send("Not enough")

    user["coins"] -= price
    user["ginv"][item] = user["ginv"].get(item,0)+1
    save(DATA_FILE,data)

    await ctx.send("Bought")

@bot.command()
async def globalinventory(ctx):
    data = get_data()
    user = get_user(data, ctx.author.id)

    inv = user["ginv"]
    msg = "\n".join([f"{k} x{v}" for k,v in inv.items()])
    await ctx.send(msg or "Empty")

# ================= SERVER SHOP =================

@bot.command()
async def additem(ctx, name, price:int):
    if not is_owner(ctx):
        return
    data = get_data()
    server = get_server(data, ctx.guild.id)
    server["shop"][name] = price
    save(DATA_FILE,data)
    await ctx.send("Added")

@bot.command()
async def shop(ctx):
    data = get_data()
    server = get_server(data, ctx.guild.id)
    msg = "\n".join([f"{k}-{v}" for k,v in server["shop"].items()])
    await ctx.send(msg or "Empty")

@bot.command()
async def buy(ctx, item):
    data = get_data()
    server = get_server(data, ctx.guild.id)
    user = get_user(data, ctx.author.id)

    if item not in server["shop"]:
        return await ctx.send("Not found")

    price = server["shop"][item]
    if user["coins"] < price:
        return await ctx.send("Not enough")

    user["coins"] -= price
    server["inv"].setdefault(str(ctx.author.id),{})
    inv = server["inv"][str(ctx.author.id)]
    inv[item] = inv.get(item,0)+1

    save(DATA_FILE,data)
    await ctx.send("Bought")

@bot.command()
async def inventory(ctx):
    data = get_data()
    server = get_server(data, ctx.guild.id)

    inv = server["inv"].get(str(ctx.author.id),{})
    msg = "\n".join([f"{k} x{v}" for k,v in inv.items()])
    await ctx.send(msg or "Empty")

# ================= LOTTERY =================

@bot.command()
async def lottery(ctx):
    data = get_data()
    user = get_user(data, ctx.author.id)

    if random.choice([True,False]):
        win = random.randint(50,200)
        user["coins"] += win
        msg = f"Won {win}"
    else:
        msg = "Lost"

    save(DATA_FILE,data)
    await ctx.send(msg)

# ================= REDEEM =================

@bot.command()
async def createcode(ctx, code, amount:int):
    if not is_owner(ctx):
        return
    codes = load(CODES_FILE)
    codes[code] = amount
    save(CODES_FILE,codes)
    await ctx.send("Code created")

@bot.command()
async def redeem(ctx, code):
    codes = load(CODES_FILE)
    data = get_data()

    if code not in codes:
        return await ctx.send("Invalid")

    user = get_user(data, ctx.author.id)
    user["coins"] += codes[code]

    del codes[code]
    save(CODES_FILE,codes)
    save(DATA_FILE,data)

    await ctx.send("Redeemed")

# ================= OWNERS =================

@bot.command()
async def addowner(ctx, member: discord.Member):
    if ctx.author.id != MAIN_OWNER:
        return
    owners = load(OWNERS_FILE)
    owners[str(member.id)] = True
    save(OWNERS_FILE,owners)
    await ctx.send("Owner added")

@bot.command()
async def removeowner(ctx, member: discord.Member):
    if ctx.author.id != MAIN_OWNER:
        return
    owners = load(OWNERS_FILE)
    owners.pop(str(member.id),None)
    save(OWNERS_FILE,owners)
    await ctx.send("Removed")

@bot.command()
async def owners(ctx):
    owners = load(OWNERS_FILE)
    msg = ""
    for uid in owners:
        u = await bot.fetch_user(int(uid))
        msg += f"{u.name}\n"
    await ctx.send(msg or "None")

# ================= TEMP OWNER =================

@bot.command()
async def tempowner(ctx, member: discord.Member, seconds:int):
    if ctx.author.id != MAIN_OWNER:
        return

    temp_owners[member.id] = time.time() + seconds
    await ctx.send(f"{member.name} is temp owner for {seconds}s")

# ================= RESET =================

@bot.command()
async def resetserver(ctx):
    if not is_owner(ctx):
        return
    data = get_data()
    data["servers"][str(ctx.guild.id)] = {"shop":{}, "inv":{}}
    save(DATA_FILE,data)
    await ctx.send("Server reset")

@bot.command()
async def resetglobal(ctx):
    if ctx.author.id != MAIN_OWNER:
        return
    data = get_data()
    data["global_shop"] = {}
    save(DATA_FILE,data)
    await ctx.send("Global reset")

# ================= HELP =================

@bot.command()
async def help(ctx):
    await ctx.send("Use commands properly 😈")

@bot.command()
async def ownerhelp(ctx):
    if not is_owner(ctx):
        return
    await ctx.send("Owner cmds: take, addglobalitem, createcode, tempowner, resetserver, resetglobal")

# ================= RUN =================

if TOKEN is None:
    print("❌ TOKEN is missing!")
else:
    print("✅ TOKEN loaded")

bot.run(TOKEN)

import math
import sys

import discord
import tabulate
from redbot.core import commands, Config
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


class EmojiTracker(commands.Cog):
    """
    Track emojis and view leaderboards/most emojis used ect..

    This cog will track reactions added to other user's messages.
    It will ignore reactions added to a bot's message
    It will also only count one reaction per emoji for each user on a message so user's can't spam react/unreact
    """
    __author__ = "Vertyco"
    __version__ = "0.0.1"

    def format_help_for_context(self, ctx):
        helpcmd = super().format_help_for_context(ctx)
        return f"{helpcmd}\nCog Version: {self.__version__}\nAuthor: {self.__author__}"

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        """No data to delete"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 117, force_registration=True)
        default_global = {"blacklist": []}
        default_guild = {"users": {}}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.reacted = {}

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Ignore reactions added by the bot
        if payload.user_id == self.bot.user.id:
            return
        # Ignore reactions added in DMs
        if not payload.guild_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        # Ignore blacklisted guilds
        blacklist = await self.config.blacklist()
        if guild.id in blacklist:
            return
        user = payload.member
        if not user:
            return
        # Ignore reactions added by other bots
        if user.bot:
            return
        chan = guild.get_channel(payload.channel_id)
        if not chan:
            return
        try:
            msg = await chan.fetch_message(payload.message_id)
            if not msg:
                return
        except (discord.NotFound, discord.Forbidden):
            return
        # Ignore reactions added to a message that a bot sent
        if msg.author.bot:
            return
        # Ignore people adding reactions to their own messages
        if msg.author.id == user.id:
            return

        emoji = str(payload.emoji)
        uid = str(user.id)
        mid = str(msg.id)

        # Only allow one reaction count per emoji on a message so users cant unreact and add the same emoji
        # This may eat up cache over time for bots with a long ass uptime and in massive servers
        if uid not in self.reacted:
            self.reacted[uid] = {}
        if mid not in self.reacted[uid]:
            self.reacted[uid][mid] = []
        if emoji in self.reacted[uid][mid]:
            return
        else:
            self.reacted[uid][mid].append(mid)

        async with self.config.guild(guild).users() as users:
            if uid not in users:
                users[uid] = {}
            if emoji not in users[uid]:
                users[uid][emoji] = 1
            else:
                users[uid][emoji] += 1

    @commands.command(name="ignoreguild")
    @commands.is_owner()
    async def blacklist_guild(
        self, ctx: commands.Context, add_or_remove: commands.Literal["add", "remove"], guild_ids: commands.Greedy[int] = None
    ):
        """
        Add/Remove guilds from the blacklist

        `<add_or_remove>` should be either `add` to add GUILD IDs or `remove` to remove GUILD IDs.
        """
        if guild_ids is None:
            return await ctx.send("`Guild_ids` is a required argument.")
        
        async with self.config.blacklist() as bl:
            for guild_id in guild_ids:
                if add_or_remove.lower() == "add":
                    if not guild_id in bl:
                        l.append(guild_id)
                        
                elif add_or_remove.lower() == "remove":
                    if guild_id in bl:
                        bl.remove(guild_id)
                        
        return await ctx.send(
            f"Successfully {'added' if add_or_remove.lower() == 'add' else 'removed'} {len([role for role in roles])} guilds {'to' if add_or_remove.lower() == 'add' else 'from'} the blacklist."
        )

    @commands.command(name="viewblacklist")
    @commands.is_owner()
    async def view_settings(self, ctx):
        """View EmojiTracker Blacklist"""
        bl = await self.config.blacklist()
        blacklist = ""
        for guild_id in bl:
            blacklist += f"{guild_id}"
        if not blacklist:
            return await ctx.send("No guild ID's have been added to the blacklist")
        embed = discord.Embed(
            title="Emoji Tracker Blacklist",
            description=f"```py\b{blacklist}\n```"
        )
        await ctx.send(embed=embed)

    @commands.command(name="resetreacts")
    @commands.guild_only()
    @commands.admin()
    async def reset_reactions(self, ctx):
        """Reset reaction data for this guild"""
        await self.config.guild(ctx.guild).clear()
        await ctx.tick()

    @commands.command(name="emojilb")
    @commands.guild_only()
    async def emoji_lb(self, ctx):
        """View the emoji leaderboard"""
        users = await self.config.guild(ctx.guild).users()
        emojis = {}
        total_emojis = 0
        for data in users.values():
            for emoji, count in data.items():
                if emoji not in emojis:
                    emojis[emoji] = count
                else:
                    emojis[emoji] += count
                total_emojis += count
        sorted_emojis = sorted(emojis.items(), key=lambda x: x[1], reverse=True)
        pages = math.ceil(len(sorted_emojis) / 10)
        start = 0
        stop = 10
        color = discord.Color.random()
        embeds = []
        for p in range(pages):
            if stop > len(sorted_emojis):
                stop = len(sorted_emojis)
            top = ""
            for i in range(start, stop, 1):
                emoji = sorted_emojis[i][0]
                count = sorted_emojis[i][1]
                top += f"{emoji} - `{count}`\n"
            embed = discord.Embed(
                title="Emoji Leaderboard",
                description=f"Total Reactions: {'{:,}'.format(total_emojis)}\n{top}",
                color=color
            )
            embed.set_footer(text=f"Pages {p + 1}/{pages}")
            embeds.append(embed)
            start += 10
            stop += 10
        if not embeds:
            return await ctx.send("No reactions saved yet!")
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.command(name="reactlb")
    @commands.guild_only()
    async def reaction_lb(self, ctx):
        """View user leaderboard for most emojis added"""
        users = await self.config.guild(ctx.guild).users()
        lb = {}
        total_reactions = 0
        for uid, data in users.items():
            user = ctx.guild.get_member(int(uid))
            if not user:
                continue
            user = user.name
            if user not in lb:
                lb[user] = 0
            for count in data.values():
                lb[user] += count
                total_reactions += count
        sorted_reactions = sorted(lb.items(), key=lambda x: x[1], reverse=True)
        pages = math.ceil(len(sorted_reactions) / 10)
        start = 0
        stop = 10
        color = discord.Color.random()
        embeds = []
        for p in range(pages):
            if stop > len(sorted_reactions):
                stop = len(sorted_reactions)
            table = []
            for i in range(start, stop, 1):
                user = sorted_reactions[i][0]
                count = sorted_reactions[i][1]
                table.append([count, user])
            top = tabulate.tabulate(table, tablefmt="presto")
            embed = discord.Embed(
                title="Reaction Leaderboard",
                description=f"Total Reactions: {'{:,}'.format(total_reactions)}\n```py\n{top}\n```",
                color=color
            )
            embed.set_footer(text=f"Pages {p + 1}/{pages}")
            embeds.append(embed)
            start += 10
            stop += 10
        if not embeds:
            return await ctx.send("No reactions saved yet!")
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.command(name="emojitrackercache", aliases=["etc"])
    @commands.is_owner()
    async def get_reaction_cache(self, ctx):
        """Get the size of EmojiTracker cache"""
        size = sys.getsizeof(self.reacted)
        if size > 1000:
            formatted = "{:,}".format(round(size / 1000, 2))
            inc = "KB"
        elif size > 1000000:
            formatted = "{:,}".format(round(size / 1000000, 2))
            inc = "MB"
        else:
            formatted = "{:,}".format(size)
            inc = "Bytes"
        await ctx.send(f"EmojiTracker Cache Size: `{formatted} {inc}`")

import nextcord
from nextcord.ext import commands, tasks
from util.eos import AsaProtocol
from util.monitorlogic import (
    save_info,
    load_info,
    update_info,
    clear_servers
)
import logging

class MonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Required info for EOS Protocol
        self.client_id = 'xyza7891muomRmynIIHaJB9COBKkwj6n'
        self.client_secret = 'PP5UGxysEieNfSrEicaD1N2Bb3TdXuD7xHYcsdUHZ7s'
        self.deployment_id = 'ad9a8feffb3b4b2ca315546f038c3ae2'
        self.epic_api = 'https://api.epicgames.dev'
        self.asa_protocol = AsaProtocol(self.client_id, self.client_secret, self.deployment_id, self.epic_api)
        # Task start for server status.
        self.update_server_status.start()

    # Time before each server querty.
    @tasks.loop(minutes=5)
    async def update_server_status(self):
        logging.info(f"Fetching server information.")
        for guild in self.bot.guilds:
            guild_info_list = load_info(guild.id)
            if guild_info_list:
                for guild_info in guild_info_list:
                    channel = self.bot.get_channel(int(guild_info['channel_id']))
                    if channel:
                        try:
                            message = await channel.fetch_message(int(guild_info['message_id']))
                            server_info = await self.asa_protocol.query(guild_info['server']['host'], guild_info['server']['port'])
                            embed = self.create_embed(server_info)
                            await message.edit(embed=embed)
                        except nextcord.NotFound:
                            # When message is not found, attempt to repost it.
                            try:
                                server_info = await self.asa_protocol.query(guild_info['server']['host'], guild_info['server']['port'])
                                embed = self.create_embed(server_info)
                                new_message = await channel.send(embed=embed)
                                update_info(guild.id, channel.id, new_message.id, guild_info['server']['host'], guild_info['server']['port'])
                            except Exception as e:
                                logging.error(f"Error reposting server status for guild {guild.id}: {e}")
                        except Exception as e:
                            logging.error(f"Error updating server status for guild {guild.id}: {e}")

    @update_server_status.before_loop
    async def before_update_server_status(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.update_server_status.cancel()
    
    @nextcord.slash_command(
        name="postserver",
        description='Create looping embed of your server status.',
        default_member_permissions=nextcord.Permissions(administrator=True),
        dm_permission=False
    )
    async def postserver(self, interaction: nextcord.Interaction, host: str, port: int, channel: nextcord.TextChannel):
        try:
            server_info = await self.asa_protocol.query(host, port)
            embed = self.create_embed(server_info)
            message = await channel.send(embed=embed)
            save_info(interaction.guild_id, channel.id, message.id, host, port)
            await interaction.response.send_message(f"Server status sent to {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error fetching server status: {e}", ephemeral=True)
    
    # Weird embed, it does need updating.
    def create_embed(self, server_info):
        embed = nextcord.Embed(title=server_info['nameversion'], color=nextcord.Color.blue())
        embed.add_field(name="Map", value=server_info['map'], inline=True)
        embed.add_field(name="Players", value=f"{server_info['numplayers']}/{server_info['maxplayers']}", inline=True)
        embed.add_field(name="Latency", value=server_info['ping'], inline=True)
        embed.add_field(name="Connect", value=server_info['connect'], inline=True)
        embed.add_field(name="Password", value="Yes" if server_info['password'] else "No", inline=True)
        embed.add_field(name="Platform", value=server_info['platform'], inline=True)
        #embed.set_image(url="https://cdn.cloudflare.steamstatic.com/steam/apps/2399830/header.jpg?t=1699643475")

        return embed

    @nextcord.slash_command(
        name="clearservers",
        description="Clear all server monitoring data.",
        default_member_permissions=nextcord.Permissions(administrator=True),
        dm_permission=False
    )
    async def clearserverdata(self, interaction: nextcord.Interaction):
        try:
            clear_servers()
            self.update_server_status.cancel()
            await interaction.response.send_message("All server monitoring data has been cleared and updates have been halted.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to clear server data: {e}", ephemeral=True)

def setup(bot):
    cog = MonitorCog(bot)
    bot.add_cog(cog)
    if not hasattr(bot, 'all_slash_commands'):
        bot.all_slash_commands = []
    bot.all_slash_commands.extend([cog.postserver, cog.clearserverdata])

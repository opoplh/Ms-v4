import random
import logging
import subprocess
import sys
import os
import re
import time
import concurrent.futures
import discord
from discord.ext import commands, tasks
import docker
import asyncio
from discord import app_commands

TOKEN = ''  # TOKEN HERE
RAM_LIMIT = '2g'
SERVER_LIMIT = 12
database_file = 'database.txt'

intents = discord.Intents.default()
intents.messages = False
intents.message_content = False

bot = commands.Bot(command_prefix='/', intents=intents)
client = docker.from_env()

# Embed color constant
EMBED_COLOR = 0x9B59B6  # Purple color

def generate_random_port():
    return random.randint(1025, 65535)

def add_to_database(user, container_name, ssh_command):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_command}\n")

def remove_from_database(ssh_command):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if ssh_command not in line:
                f.write(line)

async def capture_ssh_session_line(process):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if "ssh session:" in output:
            return output.split("ssh session:")[1].strip()
    return None

def get_ssh_command_from_database(container_id):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if container_id in line:
                return line.split('|')[2]
    return None

def get_user_servers(user):
    if not os.path.exists(database_file):
        return []
    servers = []
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                servers.append(line.strip())
    return servers

def count_user_servers(user):
    return len(get_user_servers(user))

def get_container_id_from_database(user):
    servers = get_user_servers(user)
    if servers:
        return servers[0].split('|')[1]
    return None

@bot.event
async def on_ready():
    change_status.start()
    print(f'✨ Bot is ready. Logged in as {bot.user} ✨')
    await bot.tree.sync()

@tasks.loop(seconds=5)
async def change_status():
    try:
        if os.path.exists(database_file):
            with open(database_file, 'r') as f:
                lines = f.readlines()
            instance_count = len(lines)
        else:
            instance_count = 0

        statuses = [  
            f"🌌 Managing {instance_count} Cloud Instances",  
            f"⚡ Powering {instance_count} Servers",  
            f"🔮 Watching over {instance_count} VMs"  
        ]  
        await bot.change_presence(activity=discord.Game(name=random.choice(statuses)))  
    except Exception as e:  
        print(f"💥 Failed to update status: {e}")

async def regen_ssh_command(interaction: discord.Interaction, container_name: str):
    user = str(interaction.user)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:  
        embed = discord.Embed(  
            title="🚫 Instance Not Found",  
            description="No active instance found for your user.",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)  
        return  

    try:  
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",  
                                                     stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)  
    except subprocess.CalledProcessError as e:  
        embed = discord.Embed(  
            title="⚠️ Command Error",  
            description=f"Error executing tmate in Docker container:\n```{e}```",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)  
        return  

    ssh_session_line = await capture_ssh_session_line(exec_cmd)  
    if ssh_session_line:  
        dm_embed = discord.Embed(  
            title="🔑 New SSH Session Generated",  
            description=f"```{ssh_session_line}```",  
            color=EMBED_COLOR  
        )  
        dm_embed.set_footer(text="Keep this secure and don't share it with anyone!")  
          
        response_embed = discord.Embed(  
            title="✅ Success",  
            description="New SSH session generated. Check your DMs for details!",  
            color=EMBED_COLOR  
        )  
          
        await interaction.user.send(embed=dm_embed)  
        await interaction.response.send_message(embed=response_embed)  
    else:  
        embed = discord.Embed(  
            title="❌ Failed",  
            description="Failed to generate new SSH session. Please try again.",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)

async def start_server(interaction: discord.Interaction, container_name: str):
    user = str(interaction.user)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:  
        embed = discord.Embed(  
            title="🚫 Instance Not Found",  
            description="No instance found for your user.",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)  
        return  

    try:  
        subprocess.run(["docker", "start", container_id], check=True)  
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",  
                                                     stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)  
        ssh_session_line = await capture_ssh_session_line(exec_cmd)  
        if ssh_session_line:  
            dm_embed = discord.Embed(  
                title="🚀 Instance Started",  
                description=f"**SSH Session Command:**\n```{ssh_session_line}```",  
                color=EMBED_COLOR  
            )  
            dm_embed.add_field(name="Status", value="🟢 Online", inline=True)  
            dm_embed.add_field(name="RAM", value="2GB", inline=True)  
            dm_embed.add_field(name="CPU", value="2 Cores", inline=True)  
              
            response_embed = discord.Embed(  
                title="✅ Success",  
                description="Instance started successfully! Check your DMs for details.",  
                color=EMBED_COLOR  
            )  
              
            await interaction.user.send(embed=dm_embed)  
            await interaction.response.send_message(embed=response_embed)  
        else:  
            embed = discord.Embed(  
                title="⚠️ Partial Success",  
                description="Instance started, but failed to get SSH session line.",  
                color=EMBED_COLOR  
            )  
            await interaction.response.send_message(embed=embed)  
    except subprocess.CalledProcessError as e:  
        embed = discord.Embed(  
            title="❌ Error",  
            description=f"Error starting instance:\n```{e}```",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)

async def stop_server(interaction: discord.Interaction, container_name: str):
    user = str(interaction.user)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:  
        embed = discord.Embed(  
            title="🚫 Instance Not Found",  
            description="No instance found for your user.",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)  
        return  

    try:  
        subprocess.run(["docker", "stop", container_id], check=True)  
        embed = discord.Embed(  
            title="🛑 Instance Stopped",  
            description="Instance stopped successfully!",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)  
    except subprocess.CalledProcessError as e:  
        embed = discord.Embed(  
            title="❌ Error",  
            description=f"Error stopping instance:\n```{e}```",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)

async def restart_server(interaction: discord.Interaction, container_name: str):
    user = str(interaction.user)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:  
        embed = discord.Embed(  
            title="🚫 Instance Not Found",  
            description="No instance found for your user.",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)  
        return  

    try:  
        subprocess.run(["docker", "restart", container_id], check=True)  
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",  
                                                     stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)  
        ssh_session_line = await capture_ssh_session_line(exec_cmd)  
        if ssh_session_line:  
            dm_embed = discord.Embed(  
                title="🔄 Instance Restarted",  
                description=f"**SSH Session Command:**\n```{ssh_session_line}```\n**OS:** Ubuntu 22.04",  
                color=EMBED_COLOR  
            )  
            dm_embed.add_field(name="Status", value="🟡 Restarting", inline=True)  
            dm_embed.add_field(name="RAM", value="2GB", inline=True)  
            dm_embed.add_field(name="CPU", value="2 Cores", inline=True)  
              
            response_embed = discord.Embed(  
                title="✅ Success",  
                description="Instance restarted successfully! Check your DMs for details.",  
                color=EMBED_COLOR  
            )  
              
            await interaction.user.send(embed=dm_embed)  
            await interaction.response.send_message(embed=response_embed)  
        else:  
            embed = discord.Embed(  
                title="⚠️ Partial Success",  
                description="Instance restarted, but failed to get SSH session line.",  
                color=EMBED_COLOR  
            )  
            await interaction.response.send_message(embed=embed)  
    except subprocess.CalledProcessError as e:  
        embed = discord.Embed(  
            title="❌ Error",  
            description=f"Error restarting instance:\n```{e}```",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)

def get_container_id_from_database(user, container_name):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user) and container_name in line:
                return line.split('|')[1]
    return None

async def execute_command(command):
    process = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode(), stderr.decode()

async def capture_output(process, keyword):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if keyword in output:
            return output
    return None

async def create_server_task(interaction, image, os_name):
    embed = discord.Embed(
        title=f"⚙️ Creating {os_name} Instance",
        description=f"Please wait while we create your {os_name} instance...",
        color=EMBED_COLOR
    )
    await interaction.response.send_message(embed=embed)

    user = str(interaction.user)  
    if count_user_servers(user) >= SERVER_LIMIT:  
        embed = discord.Embed(  
            title="🚫 Limit Reached",  
            description="You've reached your instance limit!",  
            color=EMBED_COLOR  
        )  
        await interaction.followup.send(embed=embed)  
        return  

    try:  
        container_id = subprocess.check_output([  
            "docker", "run", "-itd", "--privileged", "--cap-add=ALL", image  
        ]).strip().decode('utf-8')  
    except subprocess.CalledProcessError as e:  
        embed = discord.Embed(  
            title="❌ Creation Failed",  
            description=f"Error creating Docker container:\n```{e}```",  
            color=EMBED_COLOR  
        )  
        await interaction.followup.send(embed=embed)  
        return  

    try:  
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",  
                                                      stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)  
    except subprocess.CalledProcessError as e:  
        embed = discord.Embed(  
            title="❌ SSH Setup Failed",  
            description=f"Error executing tmate in Docker container:\n```{e}```",  
            color=EMBED_COLOR  
        )  
        await interaction.followup.send(embed=embed)  
        subprocess.run(["docker", "kill", container_id])  
        subprocess.run(["docker", "rm", container_id])  
        return  

    ssh_session_line = await capture_ssh_session_line(exec_cmd)  
    if ssh_session_line:  
        dm_embed = discord.Embed(  
            title=f"🎉 {os_name} Instance Created",  
            description=f"**SSH Session Command:**\n```{ssh_session_line}```",  
            color=EMBED_COLOR  
        )  
        dm_embed.add_field(name="OS", value=os_name, inline=True)  
        dm_embed.add_field(name="RAM", value="2GB", inline=True)  
        dm_embed.add_field(name="CPU", value="2 Cores", inline=True)  
        dm_embed.set_footer(text="This instance will auto-delete after 4 hours of inactivity")  
          
        response_embed = discord.Embed(  
            title="✅ Success",  
            description=f"{os_name} instance created successfully! Check your DMs for details.",  
            color=EMBED_COLOR  
        )  
          
        await interaction.user.send(embed=dm_embed)  
        add_to_database(user, container_id, ssh_session_line)  
        await interaction.followup.send(embed=response_embed)  
    else:  
        embed = discord.Embed(  
            title="⚠️ Timeout",  
            description="Instance creation is taking longer than expected. Please try again later.",  
            color=EMBED_COLOR  
        )  
        await interaction.followup.send(embed=embed)  
        subprocess.run(["docker", "kill", container_id])  
        subprocess.run(["docker", "rm", container_id])

@bot.tree.command(name="deploy-ubuntu", description="🚀 Creates a new Instance with Ubuntu 22.04")
async def deploy_ubuntu(interaction: discord.Interaction):
    await create_server_task(interaction, "ubuntu-vps", "Ubuntu 22.04")

@bot.tree.command(name="deploy-debian", description="🚀 Creates a new Instance with Debian 12")
async def deploy_debian(interaction: discord.Interaction):
    await create_server_task(interaction, "debian-vps", "Debian 12")

@bot.tree.command(name="deploy-alpine", description="🚀 Creates a new Instance with Alpine Linux")
async def deploy_alpine(interaction: discord.Interaction):
    await create_server_task(interaction, "alpine-vps", "Alpine Linux")

@bot.tree.command(name="deploy-arch", description="🚀 Creates a new Instance with Arch Linux")
async def deploy_arch(interaction: discord.Interaction):
    await create_server_task(interaction, "arch-vps", "Arch Linux")

@bot.tree.command(name="deploy-kali", description="🚀 Creates a new Instance with Kali Linux")
async def deploy_kali(interaction: discord.Interaction):
    await create_server_task(interaction, "kali-vps", "Kali Linux")

@bot.tree.command(name="deploy-fedora", description="🚀 Creates a new Instance with Fedora")
async def deploy_fedora(interaction: discord.Interaction):
    await create_server_task(interaction, "fedora-vps", "Fedora")

@bot.tree.command(name="regen-ssh", description="🔑 Generates a new SSH session for your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def regen_ssh(interaction: discord.Interaction, container_name: str):
    await regen_ssh_command(interaction, container_name)

@bot.tree.command(name="start", description="🟢 Starts your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def start(interaction: discord.Interaction, container_name: str):
    await start_server(interaction, container_name)

@bot.tree.command(name="stop", description="🛑 Stops your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def stop(interaction: discord.Interaction, container_name: str):
    await stop_server(interaction, container_name)

@bot.tree.command(name="restart", description="🔄 Restarts your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def restart(interaction: discord.Interaction, container_name: str):
    await restart_server(interaction, container_name)

@bot.tree.command(name="ping", description="🏓 Check the bot's latency.")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"⚡ Bot latency: {latency}ms",
        color=EMBED_COLOR
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="list", description="📜 Lists all your Instances")
async def list_servers(interaction: discord.Interaction):
    user = str(interaction.user)
    servers = get_user_servers(user)
    if servers:
        embed = discord.Embed(
            title=f"📋 Your Instances ({len(servers)}/{SERVER_LIMIT})",
            color=EMBED_COLOR
        )
        for server in servers:
            _, container_name, ssh_cmd = server.split('|')
            os_type = "Unknown"
            if "ubuntu" in ssh_cmd.lower():
                os_type = "Ubuntu 22.04"
            elif "debian" in ssh_cmd.lower():
                os_type = "Debian 12"
            elif "alpine" in ssh_cmd.lower():
                os_type = "Alpine Linux"
            elif "arch" in ssh_cmd.lower():
                os_type = "Arch Linux"
            elif "kali" in ssh_cmd.lower():
                os_type = "Kali Linux"
            elif "fedora" in ssh_cmd.lower():
                os_type = "Fedora"
                
            embed.add_field(
                name=f"🖥️ {container_name}",
                value=f"▫️ OS: {os_type}\n▫️ RAM: 2GB\n▫️ CPU: 2 Cores",
                inline=False
            )
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="📭 No Instances Found",
            description="You don't have any active instances.",
            color=EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remove", description="❌ Removes an Instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def remove_server(interaction: discord.Interaction, container_name: str):
    user = str(interaction.user)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:  
        embed = discord.Embed(  
            title="🚫 Instance Not Found",  
            description="No Instance found for your user with that name.",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)  
        return  

    try:  
        subprocess.run(["docker", "stop", container_id], check=True)  
        subprocess.run(["docker", "rm", container_id], check=True)  
          
        remove_from_database(container_id)  
          
        embed = discord.Embed(  
            title="🗑️ Instance Removed",  
            description=f"Instance '{container_name}' was successfully removed.",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)  
    except subprocess.CalledProcessError as e:  
        embed = discord.Embed(  
            title="❌ Removal Failed",  
            description=f"Error removing instance:\n```{e}```",  
            color=EMBED_COLOR  
        )  
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="ℹ️ Shows the help message")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="ℹ️ Cloud Instance Bot Help",
        description="Here are all the available commands:",
        color=EMBED_COLOR
    )

    commands_list = [  
        ("🚀 /deploy-ubuntu", "Creates a new Ubuntu 22.04 instance"),  
        ("🚀 /deploy-debian", "Creates a new Debian 12 instance"),  
        ("🚀 /deploy-alpine", "Creates a new Alpine Linux instance"),  
        ("🚀 /deploy-arch", "Creates a new Arch Linux instance"),  
        ("🚀 /deploy-kali", "Creates a new Kali Linux instance"),  
        ("🚀 /deploy-fedora", "Creates a new Fedora instance"),  
        ("🗑️ /remove <name>", "Removes a server"),  
        ("🟢 /start <name>", "Start a server"),  
        ("🛑 /stop <name>", "Stop a server"),  
        ("🔑 /regen-ssh <name>", "Regenerates SSH credentials"),  
        ("🔄 /restart <name>", "Restart a server"),  
        ("📜 /list", "List all your servers"),  
        ("🏓 /ping", "Check the bot's latency"),  
        ("ℹ️ /help", "Show this help message")  
    ]  
    
    for cmd, desc in commands_list:  
        embed.add_field(name=cmd, value=desc, inline=False)  
    
    embed.set_footer(text="Need more help? Contact server staff!")  
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)

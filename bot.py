import os
import sys
import traceback
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# =============================================================================
# 1. VARIÁVEIS DE AMBIENTE (.env)
# =============================================================================
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Removida a obrigatoriedade do CANAL_REGISTROS_ID para o bot iniciar
if not DISCORD_TOKEN:
    print("[ERRO FATAL] DISCORD_TOKEN ausente no Render!", flush=True)
    sys.exit(1)

# =============================================================================
# 2. SERVIDOR HTTP PARA MANTER O RENDER ATIVO (FREE TIER)
# =============================================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot Farm Operacional!")

    def log_message(self, format, *args):
        return

def iniciar_servidor_web():
    try:
        porta = int(os.environ.get("PORT", 8080))
        servidor = HTTPServer(("0.0.0.0", porta), HealthCheckHandler)
        print(f"[WEB] Servidor HTTP escutando na porta {porta}...", flush=True)
        servidor.serve_forever()
    except Exception as e:
        print(f"[WEB] Erro no servidor: {e}", flush=True)

threading.Thread(target=iniciar_servidor_web, daemon=True).start()

# =============================================================================
# 3. MODAL SIMPLIFICADO (ALTERADO: ENVIA NO CANAL DE ORIGEM)
# =============================================================================
class FarmModal(discord.ui.Modal):
    quantidade = discord.ui.TextInput(
        label="Quantidade Entregue",
        placeholder="Ex: 50",
        style=discord.TextStyle.short,
        min_length=1,
        max_length=10,
        required=True
    )
    observacoes = discord.ui.TextInput(
        label="Observações (Opcional)",
        placeholder="Ex: Guardado no baú da facção / Turno da noite",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=False
    )

    def __init__(self, bot_instance: commands.Bot, canal_id: int, item_escolhido: str, emoji_item: str) -> None:
        super().__init__(title=f"📋 Registrar: {item_escolhido}")
        self.bot = bot_instance
        self.canal_id = canal_id  # Agora armazena o canal onde o comando foi digitado
        self.item_escolhido = item_escolhido
        self.emoji_item = emoji_item

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            # Busca o canal onde o comando foi executado
            canal = self.bot.get_channel(self.canal_id)
            if not canal:
                canal = await self.bot.fetch_channel(self.canal_id)
            
            qtd_digitada = self.quantidade.value.strip()
            obs_texto = self.observacoes.value.strip() if self.observacoes.value else "Nenhuma observação informada."

            embed = discord.Embed(
                title="📦 Novo Registro de Farm Recebido",
                description=f"Registro formalizado pelo membro {interaction.user.mention}.",
                color=discord.Color.green(),
                timestamp=interaction.created_at
            )

            embed.add_field(name=f"{self.emoji_item} Item Farmado", value=f"**{self.item_escolhido}**", inline=False)
            embed.add_field(name="🛒 Quantidade", value=f"**{qtd_digitada} un.**", inline=False)
            embed.add_field(name="📅 Horário", value=f"<t:{int(interaction.created_at.timestamp())}:F>", inline=False)
            embed.add_field(name="📝 Observações", value=f"_{obs_texto}_", inline=False)

            avatar_url = interaction.user.display_avatar.url if interaction.user.display_avatar else None
            embed.set_author(name=interaction.user.display_name, icon_url=avatar_url)
            embed.set_footer(text="FarmBot • Sistema de Gestão de Farm")

            # Envia a embed pública no canal onde o comando foi digitado
            await canal.send(embed=embed)

            # Resposta privada de sucesso para quem usou o comando
            await interaction.followup.send(
                f"✅ **Seu registro de farm foi postado com sucesso!**\n"
                f"• Item: **{self.emoji_item} {self.item_escolhido}**\n"
                f"• Quantidade: **{qtd_digitada} un.**\n"
                f"• Canal: {canal.mention}", 
                ephemeral=True
            )
            print(f"[SUCESSO] Farm de {self.item_escolhido} postado em #{canal.name}", flush=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ **Erro de Permissão:** O bot não tem permissão para postar neste canal. "
                "Conceda permissões de 'Ver Canal', 'Enviar Mensagens' e 'Inserir Links' para o bot aqui.", 
                ephemeral=True
            )
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Erro inesperado: {str(e)}", ephemeral=True)

# =============================================================================
# 4. VIEW COM O MENU DROPDOWN DE SELEÇÃO ÚNICA
# =============================================================================
class FarmSelectView(discord.ui.View):
    def __init__(self, bot_instance: commands.Bot, canal_id: int) -> None:
        super().__init__(timeout=120)
        self.bot = bot_instance
        self.canal_id = canal_id

    @discord.ui.select(
        placeholder="Selecione o item que você farmou...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Ferro", description="Minério de ferro bruto ou refinado", emoji="⛏️", value="Ferro"),
            discord.SelectOption(label="Sabão", description="Sabão para limpeza ou suprimentos", emoji="🧼", value="Sabão"),
            discord.SelectOption(label="Tecido", description="Fardos e materiais têxteis", emoji="🧵", value="Tecido"),
            discord.SelectOption(label="Placa de Colete", description="Placas balísticas de proteção", emoji="🛡️", value="Placa de Colete"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        item_escolhido = select.values[0]
        icones = {"Ferro": "⛏️", "Sabão": "🧼", "Tecido": "🧵", "Placa de Colete": "🛡️"}
        emoji = icones.get(item_escolhido, "📦")
        
        # Repassa o canal dinâmico capturado para o Modal
        modal = FarmModal(
            bot_instance=self.bot,
            canal_id=self.canal_id,
            item_escolhido=item_escolhido,
            emoji_item=emoji
        )
        await interaction.response.send_modal(modal)

# =============================================================================
# 5. CONFIGURAÇÃO DO BOT COM SINCRONIZAÇÃO INSTANTÂNEA
# =============================================================================
intents = discord.Intents.default()
intents.guilds = True

class FarmBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Activity(type=discord.ActivityType.watching, name="/farmar")
        )

    async def setup_hook(self) -> None:
        await self.tree.sync()

    async def on_ready(self) -> None:
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"[DISCORD] Comandos sincronizados em: {guild.name}", flush=True)
            except Exception as e:
                print(f"[DISCORD] Erro ao sincronizar em {guild.name}: {e}", flush=True)
        print(f"[DISCORD] Bot online com sucesso como: {self.user} (ID: {self.user.id})", flush=True)

bot = FarmBot()

# =============================================================================
# 6. COMANDO SLASH /farmar (ALTERADO: CAPTURA O CANAL ATUAL)
# =============================================================================
@bot.tree.command(name="farmar", description="Abre o menu de seleção para registrar entrega de farm.")
async def farmar(interaction: discord.Interaction) -> None:
    # Passamos interaction.channel_id dinamicamente para a View externa
    view = FarmSelectView(bot_instance=bot, canal_id=interaction.channel_id)
    await interaction.response.send_message(
        "📦 **Selecione abaixo o item que você entregou:**",
        view=view,
        ephemeral=True
    )

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    print(f"[ERRO COMANDO] {error}", flush=True)
    traceback.print_exc()
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ Erro no comando: {error}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Erro no comando: {error}", ephemeral=True)
    except Exception:
        pass

if __name__ == "__main__":
    print("[DISCORD] Conectando ao gateway do Discord...", flush=True)
    bot.run(DISCORD_TOKEN)

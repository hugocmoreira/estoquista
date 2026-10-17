import os
import re  # Certifique-se de que "import re" está no topo do seu arquivo se for usar de forma isolada, ou apenas adicione aqui.
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
        placeholder="Ex: Print enviado abaixo. / Vou postar o print amanhã.",
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

            # Texto limpo, organizado e padronizado na descrição
            texto_formatado = (
                f"Registro formalizado pelo membro {interaction.user.mention}.\n\n"
                f"{self.emoji_item} **Item Farmado:** _{self.item_escolhido}_\n"
                f"🛒 **Quantidade:** _{qtd_digitada} un._\n\n"
                f"📅 **Data/Hora:** <t:{int(interaction.created_at.timestamp())}:F>\n\n"
                f"📝 **Observações:**\n_{obs_texto}_"
            )

            embed = discord.Embed(
                title="📦 Novo Registro de Farm Recebido",
                description=texto_formatado,
                color=discord.Color.green(),
                timestamp=interaction.created_at
            )

            avatar_url = interaction.user.display_avatar.url if interaction.user.display_avatar else None
            embed.set_author(name=interaction.user.display_name, icon_url=avatar_url)
            embed.set_footer(text="Estoquista • Sistema de Gestão de Farm")


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
        
        modal = FarmModal(
            bot_instance=self.bot,
            canal_id=self.canal_id,
            item_escolhido=item_escolhido,
            emoji_item=emoji
        )
        
        # Abre o modal para o usuário
        await interaction.response.send_modal(modal)
        
        # APÓS ENVIAR O MODAL: Atualiza a mensagem ephemeral do menu, limpando-a
        await interaction.edit_original_response(
            content="⏳ *Formulário aberto! Preencha os dados na janela que apareceu na sua tela.*", 
            view=None
        )


# =============================================================================
# 5. CONFIGURAÇÃO DO BOT COM SINCRONIZAÇÃO INSTANTÂNEA
# =============================================================================
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True  # CORREÇÃO AQUI: Ativa a intenção de ler o conteúdo das mensagens!

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
        print(f"[BOT] Conectado com sucesso como {self.user}!", flush=True)
        # Código finalizado que estava cortado no seu envio:
        for guild in self.guilds:
            try:
                await self.tree.sync(guild=discord.Object(id=guild.id))
            except Exception as e:
                print(f"[ERRO SYNC] Não foi possível sincronizar na guilda {guild.id}: {e}", flush=True)

# Instancia e roda o Bot
bot = FarmBot()

@bot.tree.command(name="farmar", description="Abre o menu para registrar o seu farm.")
async def farmar(interaction: discord.Interaction):
    # Envia o menu dropdown de forma privada (ephemeral) para quem usou o comando
    view = FarmSelectView(bot_instance=bot, canal_id=interaction.channel_id)
    await interaction.response.send_message("📋 **Menu de Registro de Farm:**", view=view, ephemeral=True)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

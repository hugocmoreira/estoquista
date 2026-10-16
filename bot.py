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
        
        # CORREÇÃO AQUI: Abre o modal para o usuário
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
# MODAL MANUAL CORRIGIDO (ESTRUTURA DE PARÂMETROS BLINDADA)
# =============================================================================
class RegistrarManualModal(discord.ui.Modal):
    item_manual = discord.ui.TextInput(
        label="Nome do Item Farmado",
        placeholder="Ex: Ferro, Sabão, Metanfetamina...",
        style=discord.TextStyle.short,
        min_length=2,
        max_length=50,
        required=True
    )
    
    quantidade = discord.ui.TextInput(
        label="Quantidade Entregue",
        placeholder="Ex: 100 (digite apenas números)",
        style=discord.TextStyle.short,
        min_length=1,
        max_length=10,
        required=True
    )
    
    observacoes = discord.ui.TextInput(
        label="Observações (Opcional)",
        placeholder="Ex: Entregue no cofre principal",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=False
    )

    # CORREÇÃO: Definido title direto no super() para evitar falha de carregamento da API
    def __init__(self, bot_instance: commands.Bot, canal_id: int) -> None:
        super().__init__(title="📋 Registro Manual de Farm")
        self.bot = bot_instance
        self.canal_id = canal_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Responde o gateway imediatamente para evitar timeout na interface
        await interaction.response.defer(ephemeral=True)
        try:
            canal = self.bot.get_channel(self.canal_id)
            if not canal:
                canal = await self.bot.fetch_channel(self.canal_id)
            
            item_digitado = self.item_manual.value.strip().capitalize()
            qtd_bruta = self.quantidade.value.strip()
            obs_texto = self.observacoes.value.strip() if self.observacoes.value else "Nenhuma observação informada."

            # Extração de segurança dos números
            qtd_filtrada = "".join(caractere for caractere in qtd_bruta if caractere.isdigit())
            if not qtd_filtrada:
                qtd_filtrada = "0"

            # Formatação idêntica para manter a compatibilidade com o /consolidar
            texto_formatado = (
                f"Registro formalizado pelo membro {interaction.user.mention}.\n\n"
                f"**Item Farmado:** _{item_digitado}_\n"
                f"**Quantidade:** _{int(qtd_filtrada)} un._\n"
                f"📅 **Horário:** <t:{int(interaction.created_at.timestamp())}:F>\n\n"
                f"📝 **Observações:**\n_{obs_texto}_"
            )

            embed = discord.Embed(
                title="📦 Novo Registro de Farm Recebido",
                description=texto_formatado,
                color=discord.Color.dark_green(),
                timestamp=interaction.created_at
            )

            avatar_url = interaction.user.display_avatar.url if interaction.user.display_avatar else None
            embed.set_author(name=interaction.user.display_name, icon_url=avatar_url)
            embed.set_footer(text="FarmBot • Sistema de Gestão de Farm")

            await canal.send(embed=embed)

            await interaction.followup.send(
                f"✅ **Seu registro manual foi postado com sucesso!**\n"
                f"• Item: **{item_digitado}**\n"
                f"• Quantidade: **{int(qtd_filtrada)} un.**\n"
                f"• Canal: {canal.mention}", 
                ephemeral=True
            )
            print(f"[MANUAL] Farm de {item_digitado} postado em #{canal.name}", flush=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ **Erro:** O bot não tem permissão para postar neste canal.", ephemeral=True)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Erro inesperado: {str(e)}", ephemeral=True)

# =============================================================================
# COMANDO SLASH /registrar CORRIGIDO (REPASSANDO OS ARGUMENTOS CORRETOS)
# =============================================================================
@bot.tree.command(name="registrar", description="Abre o formulário manual para digitar o item e a quantidade.")
async def registrar(interaction: discord.Interaction) -> None:
    # CORREÇÃO: Certifique-se de que os argumentos batem exatamente com o __init__ do modal acima!
    modal = RegistrarManualModal(bot_instance=bot, canal_id=interaction.channel_id)
    await interaction.response.send_modal(modal)


#==============================================
#novo comando Consolidar
#===============================================

@bot.tree.command(name="consolidar", description="Lê o histórico do canal e soma o total entregue por item.")
@app_commands.default_permissions(administrator=True)
async def consolidar(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=False)
    
    totais = {
        "Ferro": 0,
        "Sabão": 0,
        "Tecido": 0,
        "Placa de Colete": 0
    }
    
    regex_item = r"\*\*Item Farmado:\*\* _([^_]+)_"
    regex_qtd = r"\*\*Quantidade:\*\* _(\d+)\s*un\._"
    
    mensagens_analisadas = 0
    registros_encontrados = 0

    try:
        async for mensagem in interaction.channel.history(limit=500):
            mensagens_analisadas += 1
            
            if mensagem.author.bot and mensagem.embeds:
                message_embeds = mensagem.embeds
                for embed in message_embeds:
                    # CORREÇÃO AQUI: Garante que a embed tem o título correto e possui descrição
                    if embed.title == "📦 Novo Registro de Farm Recebido" and embed.description:
                        desc = embed.description
                        
                        # O localizador RE agora roda estritamente seguro aqui dentro
                        match_item = re.search(regex_item, desc)
                        match_qtd = re.search(regex_qtd, desc)
                        
                        if match_item and match_qtd:
                            item = match_item.group(1).strip()
                            qtd = int(match_qtd.group(1))
                            
                            if item in totais:
                                totais[item] += qtd
                                registros_encontrados += 1
                            else:
                                totais[item] = totais.get(item, 0) + qtd
                                registros_encontrados += 1

        icones = {"Ferro": "⛏️", "Sabão": "🧼", "Tecido": "🧵", "Placa de Colete": "🛡️"}
        
        texto_relatorio = "📊 **Fechamento de Estoque — Total por Item**\n"
        texto_relatorio += f"_Analisadas {mensagens_analisadas} mensagens. {registros_encontrados} registros de farm contabilizados._\n\n"
        
        for item, total in totais.items():
            emoji = icones.get(item, "📦")
            texto_relatorio += f"{emoji} **{item}:** _{total} un._\n"

        embed_resultado = discord.Embed(
            title="✅ Consolidação de Farm Concluída",
            description=texto_relatorio,
            color=discord.Color.blue(),
            timestamp=interaction.created_at
        )
        embed_resultado.set_footer(text="Estoquista • Balanço Automatizado")

        await interaction.followup.send(embed=embed_resultado)

    except discord.Forbidden:
        await interaction.followup.send("❌ **Erro:** O bot precisa da permissão 'Ver Histórico de Mensagens' para ler este canal.", ephemeral=True)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Erro ao consolidar dados: {str(e)}", ephemeral=True)

#==============================================
#novo comando Consolidar
#===============================================

@bot.tree.command(name="fechar_caixa", description="Soma todo o farm do canal dividido por USUÁRIO e limpa os registros.")
@app_commands.default_permissions(administrator=True)
async def fechar_caixa(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("⏳ *Iniciando fechamento de caixa coletivo e limpeza do canal...*", ephemeral=True)
    
    # Dicionário dinâmico para armazenar: { "MembroID": { "Item": Total } }
    dados_usuarios = {}
    
    # Expressões regulares atualizadas
    regex_membro = r"Registro formalizado pelo membro <@!?(\d+)>"
    regex_item = r"\*\*Item Farmado:\*\* _([^_]+)_"
    regex_qtd = r"\*\*Quantidade:\*\* _(\d+)\s*un\._"
    
    registros_encontrados = 0
    mensagens_para_deletar = []

    try:
        # Varre as últimas 1000 mensagens devido ao fluxo coletivo ser maior
        async for mensagem in interaction.channel.history(limit=1000):
            if mensagem.author.bot and mensagem.embeds:
                for embed in mensagem.embeds:
                    if embed.title == "📦 Novo Registro de Farm Recebido" and embed.description:
                        desc = embed.description
                        
                        match_membro = re.search(regex_membro, desc)
                        match_item = re.search(regex_item, desc)
                        match_qtd = re.search(regex_qtd, desc)
                        
                        if match_membro and match_item and match_qtd:
                            membro_id = match_membro.group(1)
                            item = match_item.group(1).strip()
                            qtd = int(match_qtd.group(1))
                            
                            # Se o membro ainda não existe no dicionário, cria a estrutura dele
                            if membro_id not in dados_usuarios:
                                dados_usuarios[membro_id] = {
                                    "Ferro": 0,
                                    "Sabão": 0,
                                    "Tecido": 0,
                                    "Placa de Colete": 0
                                }
                            
                            # Adiciona a quantidade ao item do usuário correspondente
                            if item in dados_usuarios[membro_id]:
                                dados_usuarios[membro_id][item] += qtd
                            else:
                                dados_usuarios[membro_id][item] = qtd
                            
                            registros_encontrados += 1
                            mensagens_para_deletar.append(mensagem)

        # Se nenhum registro for encontrado, avisa o ADM e para por aqui
        if registros_encontrados == 0:
            await interaction.edit_original_response(content="❌ *Nenhum registro oficial de farm foi encontrado para fechamento.*")
            return

        # 1. Montagem do relatório detalhado por Usuário
        icones = {"Ferro": "⛏️", "Sabão": "🧼", "Tecido": "🧵", "Placa de Colete": "🛡️"}
        
        texto_relatorio = "🔒 **FECHAMENTO DE CAIXA COLETIVO**\n"
        texto_relatorio += f"_Balanço geral de {registros_encontrados} formulários processados._\n\n"
        
        for membro_id, itens_farmados in dados_usuarios.items():
            texto_relatorio += f"👤 **Produtor:** <@{membro_id}>\n"
            
            # Lista apenas os itens que o usuário realmente farmou (maiores que 0)
            tem_farm = False
            for item, total in itens_farmados.items():
                if total > 0:
                    emoji = icones.get(item, "📦")
                    texto_relatorio += f" ├ {emoji} {item}: _{total} un._\n"
                    tem_farm = True
            
            if not tem_farm:
                texto_relatorio += " └ _Nenhum item contabilizado._\n"
            
            texto_relatorio += "\n" # Espaço entre um usuário e outro

        embed_resultado = discord.Embed(
            title="📥 Balanço Geral Salvo por Usuário",
            description=texto_relatorio,
            color=discord.Color.red(),
            timestamp=interaction.created_at
        )
        embed_resultado.set_footer(text=f"Fechamento por: {interaction.user.display_name}")
        
        # Envia o relatório final transparente para todo o grupo ver
        await interaction.channel.send(embed=embed_resultado)

        # 2. Executa a limpeza deletando as embeds somadas
        for msg_antiga in mensagens_para_deletar:
            try:
                await msg_antiga.delete()
            except discord.HTTPException:
                pass

        await interaction.edit_original_response(content="✅ *Caixa coletivo fechado! Os totais foram divididos por usuário e o chat foi limpo.*")

    except discord.Forbidden:
        await interaction.edit_original_response(content="❌ *Erro: O bot precisa da permissão 'Gerenciar Mensagens' para limpar o canal.*")
    except Exception as e:
        traceback.print_exc()
        await interaction.edit_original_response(content=f"❌ *Erro ao fechar caixa coletivo: {str(e)}*")

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

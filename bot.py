import os
import sys
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Carrega variáveis locais se existir o .env
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CANAL_REGISTROS_ID = os.getenv("CANAL_REGISTROS_ID")

if not DISCORD_TOKEN or not CANAL_REGISTROS_ID:
    print("[ERRO] Variáveis DISCORD_TOKEN ou CANAL_REGISTROS_ID ausentes!")
    sys.exit(1)

CANAL_REGISTROS_ID = int(CANAL_REGISTROS_ID)

# ==========================================================
# MINI SERVIDOR WEB PARA O RENDER (PORT BINDING)
# ==========================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Farm Operacional 24/7!")

    def log_message(self, format, *args):
        return  # Silencia logs de requisições HTTP para não poluir o terminal

def iniciar_servidor_web():
    porta = int(os.environ.get("PORT", 8080))
    servidor = HTTPServer(("0.0.0.0", porta), HealthCheckHandler)
    servidor.serve_forever()

# Inicia o servidor web em uma thread separada para não bloquear o bot
threading.Thread(target=iniciar_servidor_web, daemon=True).start()

# ==========================================================
# SEU CÓDIGO DO BOT (MODAL, SLASH COMMAND, ETC.)
# ==========================================================
# [Mantenha aqui as classes FarmModal, FarmBot e o comando /farmar do passo anterior]
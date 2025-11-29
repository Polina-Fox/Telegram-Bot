# -*- coding: utf-8 -*-
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import json

# ===== CONFIGURATION =====
BOT_TOKEN = "8252929537:AAHQ37iKbJ8mquoeFRTK9C1D_wtT7z_57IA"
LM_STUDIO_SERVER_URL = "http://127.0.0.1:1234/v1"
LM_STUDIO_MODEL_NAME = "qwen2.5-1.5b-instruct"

# ===== CONTEXT STORAGE =====
user_contexts = {}

# ===== LOGGING SETUP =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== LM STUDIO FUNCTIONS =====
def get_context_for_user(user_id: int) -> list:
    """Get message history for user. Create empty if not exists."""
    if user_id not in user_contexts:
        user_contexts[user_id] = [
            {"role": "system", "content": "You are a helpful and friendly assistant. Answer in Russian."}
        ]
    return user_contexts[user_id]

def add_to_context(user_id: int, role: str, content: str):
    """Add message to user context."""
    context = get_context_for_user(user_id)
    context.append({"role": role, "content": content})

def clear_context_for_user(user_id: int):
    """Clear dialog history for user."""
    if user_id in user_contexts:
        user_contexts[user_id] = [user_contexts[user_id][0]]

def generate_response_with_lm_studio(user_id: int) -> str:
    """Send user context to LM Studio and return model response."""
    context = get_context_for_user(user_id)

    url = f"{LM_STUDIO_SERVER_URL}/chat/completions"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": LM_STUDIO_MODEL_NAME,
        "messages": context,
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=60)
        response.raise_for_status()

        response_data = response.json()
        assistant_reply = response_data['choices'][0]['message']['content']
        return assistant_reply.strip()

    except requests.exceptions.RequestException as e:
        logger.error(f"LM Studio request error: {e}")
        return "Sorry, error connecting to language model. Check if LM Studio is running."
    except (KeyError, IndexError) as e:
        logger.error(f"Error parsing LM Studio response: {e}")
        return "Sorry, could not process model response."

# ===== TELEGRAM HANDLERS =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome_text = (
        "Hello! I'm an AI bot that remembers our conversation.\n"
        "Ask questions and I'll try to answer considering our chat context.\n"
        "Use /clear to clear our dialog history."
    )
    await update.message.reply_text(welcome_text)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    user_id = update.effective_user.id
    clear_context_for_user(user_id)
    await update.message.reply_text("Dialog history cleared. Let's start fresh!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages from user."""
    user_id = update.effective_user.id
    user_message = update.message.text

    logger.info(f"Message from user {user_id}: {user_message}")

    add_to_context(user_id, "user", user_message)
    await update.message.chat.send_action(action="typing")
    assistant_reply = generate_response_with_lm_studio(user_id)
    add_to_context(user_id, "assistant", assistant_reply)
    await update.message.reply_text(assistant_reply)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(msg="Exception while handling update:", exc_info=context.error)

# ===== BOT START =====
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
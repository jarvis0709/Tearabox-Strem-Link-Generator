import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import urllib.parse
from datetime import datetime, timedelta
import requests
import httpx 
from pymongo.errors import DuplicateKeyError
from pymongo import MongoClient, ASCENDING
import secrets

# Add this at the top of the file
VERIFICATION_REQUIRED = os.getenv('VERIFICATION_REQUIRED', 'true').lower() == 'true'

admin_ids = [6025969005, 6018060368]

# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb+srv://tejaschavan1110:cSxC44OLfIPxcXxp@cluster0.iu0f4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')  # Get MongoDB URI from environment variables
client = MongoClient(MONGO_URI)
db = client['terabox_bot']
users_collection = db['users']

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get the bot token and channel ID from environment variables
TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')

# Define the /start command handler
async def start(update: Update, context: CallbackContext) -> None:
    logger.info("Received /start command")
    user = update.effective_user

    # Check if the start command includes a token (for verification)
    if context.args:
        text = update.message.text
        if text.startswith("/start terabox-"):
            # Currently disabled 
            return
        token = context.args[0]
        user_data = users_collection.find_one({"user_id": user.id, "token": token})

        if user_data:
            # Update the user's verification status
            users_collection.update_one(
                {"user_id": user.id},
                {"$set": {"verified_until": datetime.now() + timedelta(days=1)}},
                upsert=True
            )
            await update.message.reply_text(
                "✅ **Verification Successful!**\n\n"
                "You can now use the bot for the next 24 hours without any ads or restrictions.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ **Invalid Token!**\n\n"
                "Please try verifying again.",
                parse_mode='Markdown'
            )
        return

    # If no token, send the welcome message and store user ID in MongoDB
    users_collection.update_one(
        {"user_id": user.id},
        {"$set": {"username": user.username, "full_name": user.full_name}},
        upsert=True
    )
    message = (
        f"New user started the bot:\n"
        f"Name: {user.full_name}\n"
        f"Username: @{user.username}\n"
        f"User   ID: {user.id}"
    )
    await context.bot.send_message(chat_id=CHANNEL_ID, text=message)
    # Corrected photo URL
    photo_url = 'https://ik.imagekit.io/dvnhxw9vq/unnamed.png?updatedAt=1735280750258'
    await update.message.reply_photo(
        photo=photo_url,
        caption=(
            "👋 **Welcome to the TeraBox Online Player!** 🌟\n\n"
        "Hello, dear user! I'm here to make your experience seamless and enjoyable.\n\n"
        "✨ **What can I do for you?**\n"
        "- Send me any TeraBox link, and I'll provide you with a direct streaming link without any ads!\n"
        "- Enjoy uninterrupted access for 24 hours with a simple verification process.\n\n"
        "🔑 **Ready to get started?** Just type your TeraBox link below, and let’s dive in!\n\n"
        "Thank you for choosing TeraBox Online Player! ❤️"
        ),
        parse_mode='Markdown'
    )

async def stats(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id in admin_ids:
        try:
            # Get total users
            total_users = users_collection.count_documents({})

            # Get MongoDB database stats
            db_stats = db.command("dbstats")

            # Calculate used storage
            used_storage_mb = db_stats['dataSize'] / (1024 ** 2)  # Convert bytes to MB

            # Calculate total and free storage (if available)
            if 'fsTotalSize' in db_stats:
                total_storage_mb = db_stats['fsTotalSize'] / (1024 ** 2)  # Convert bytes to MB
                free_storage_mb = total_storage_mb - used_storage_mb
            else:
                total_storage_in_mb = 512

                # Calculate free storage
                free_storage_in_mb = total_storage_in_mb - used_storage_mb
                # Fallback for environments where fsTotalSize is not available
                total_storage_mb = "N/A"
                free_storage_mb = free_storage_in_mb

            # Prepare the response message
            message = (
                f"📊 **Bot Statistics**\n\n"
                f"👥 **Total Users:** {total_users}\n"
                f"💾 **MongoDB Used Storage:** {used_storage_mb:.2f} MB\n"
                f"🆓 **MongoDB Free Storage:** {free_storage_mb if isinstance(free_storage_mb, str) else f'{free_storage_mb:.2f} MB'}\n"
            )

            await update.message.reply_text(message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            await update.message.reply_text("❌ An error occurred while fetching stats.")
    else:
        await update.message.reply_text("You Have No Rights To Use My Commands")

async def handle_link(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    # Check if user is admin
    if user.id in admin_ids:
        # Admin ko verify karne ki zaroorat na ho
        pass
    else:
        # User ko verify karne ki zaroorat hai
        if VERIFICATION_REQUIRED and not await check_verification(user.id):
            # User ko verify karne ki zaroorat hai
            btn = [
                [InlineKeyboardButton("Verify", url=await get_token(user.id, context.bot.username))],
                [InlineKeyboardButton("How To Open Link & Verify", url="https://t.me/how_to_download_0011")]
            ]
            await update.message.reply_text(
                text="🚨 <b>Token Expired!</b>\n\n"
                     "<b>Timeout: 24 hours</b>\n\n"
                     "Your access token has expired. Verify it to continue using the bot!\n\n"
                     "<b>🔑 Why Tokens?</b>\n\n"
                     "Tokens unlock premium features with a quick ad process. Enjoy 24 hours of uninterrupted access! 🌟\n\n"
                     "<b>👉 Tap below to verify your token.</b>\n\n"
                     "Thank you for your support! ❤️",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return

    if update.message.text.startswith('http://') or update.message.text.startswith('https://'):
        original_link = update.message.text.strip()

        # Step 1: Send "Processing..." message
        processing_msg = await update.message.reply_text("⏳ Processing your link...")

        # Step 2: Try to get the final stream link
        final_stream_link = await get_final_stream_link(original_link)

        if not final_stream_link:
            # Step 3: If failed, inform user and stop
            await processing_msg.delete()
            await update.message.reply_text("❌ Broken or unsupported link. Please send a valid TeraBox URL.")
            return

        # Step 4: Delete the "Processing..." message
        await processing_msg.delete()

        button = [
            [InlineKeyboardButton("🌐Download Server 🌐", url=final_stream_link)]
        ]
        reply_markup = InlineKeyboardMarkup(button)

        # Send the user's details and message to the channel
        user_message = (
            f"User   message:\n"
            f"Name: {update.effective_user.full_name}\n"
            f"Username: @{update.effective_user.username}\n"
            f"User   ID: {update.effective_user.id}\n"
            f"Message: {original_link}"
        )

        # Send the message with the link, copyable link, and button
        await update.message.reply_text(
            f"👇👇 YOUR VIDEO LINK IS READY, USE THESE SERVERS 👇👇\n\n♥ 👇Your Stream Link👇 ♥\n",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("Please send Me Only TeraBox Link.")

# Define the /broadcast command handler
async def broadcast(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id in admin_ids:
        message = update.message.reply_to_message
        if message:
            # Fetch all user IDs from MongoDB
            all_users = users_collection.find({}, {"user_id": 1})
            total_users = users_collection.count_documents({})
            sent_count = 0
            block_count = 0
            fail_count = 0

            for user_data in all_users:
                user_id = user_data['user_id']
                try:
                    if message.photo:
                        await context.bot.send_photo(chat_id=user_id, photo=message.photo[-1].file_id, caption=message.caption)
                    elif message.video:
                        await context.bot.send_video(chat_id=user_id, video=message.video.file_id, caption=message.caption)
                    else:
                        await context.bot.send_message(chat_id=user_id, text=message.text)
                    sent_count += 1
                except Exception as e:
                    if 'blocked' in str(e):
                        block_count += 1
                    else:
                        fail_count += 1

            await update.message.reply_text(
                f"Broadcast completed!\n\n"
                f"Total users: {total_users}\n"
                f"Messages sent: {sent_count}\n"
                f"Users blocked the bot: {block_count}\n"
                f"Failed to send messages: {fail_count}"
            )
        else:
            await update.message.reply_text("Please reply to a message with /broadcast to send it to all users.")
    else:
        await update.message.reply_text("You Have No Rights To Use My Commands")


async def check_verification(user_id: int) -> bool:
    user = users_collection.find_one({"user_id": user_id})
    if user and user.get("verified_until", datetime.min) > datetime.now():
        return True
    return False

async def get_token(user_id: int, bot_username: str) -> str:
    # Generate a random token
    token = os.urandom(16).hex()
    # Update user's verification status in database
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"token": token, "verified_until": datetime.min}},  # Reset verified_until to min
        upsert=True
    )
    # Create verification link
    verification_link = f"https://telegram.me/{bot_username}?start={token}"
    # Shorten verification link using shorten_url_link function
    shortened_link = shorten_url_link(verification_link)
    return shortened_link

async def get_final_stream_link(terabox_url: str) -> str:
    api_url = f"https://api.teleservices.io/terabox.php?url={terabox_url}"

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get(api_url)

        if response.status_code == 200:
            data = response.json()

            if data.get("status") == "success" and data.get("download_link"):
                return data["download_link"]

    except Exception as e:
        logger.error(f"Error fetching final stream link: {e}")

    return None  # Return None if anything fails


def shorten_url_link(url):
    api_url = 'https://zegalinks.com/api'
    api_key = 'f2224457b6e31324d0db8a192bcfaa71151475bb'
    params = {
        'api': api_key,
        'url': url
    }
    # Yahan pe custom certificate bundle ka path specify karo
    response = requests.get(api_url, params=params, verify=False)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            logger.info(f"Adrinolinks shortened URL: {data['shortenedUrl']}")
            return data['shortenedUrl']
    logger.error(f"Failed to shorten URL with Adrinolinks: {url}")
    return url

        
def main() -> None:
    # Get the port from the environment variable or use default
    port = int(os.environ.get('PORT', 8080))  # Default to port 8080
    webhook_url = f"https://tearabox-strem-link-generator.onrender.com/{TOKEN}"  # Replace with your server URL

    # Create the Application and pass it your bot's token
    app = ApplicationBuilder().token(TOKEN).build()

    # Register the /start command handler
    app.add_handler(CommandHandler("start", start))

    # Register the /stats command handler
    app.add_handler(CommandHandler("stats", stats))

    # Register the link handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    # Register the /broadcast command handler
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Run the bot using a webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TOKEN,
        webhook_url=webhook_url
    )

if __name__ == '__main__':
    main()

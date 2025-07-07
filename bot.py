import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    PreCheckoutQueryHandler,
    CallbackQueryHandler,
)
from config import TELEGRAM_TOKEN, TELEGRAM_PAYMENTS_PROVIDER_TOKEN
import database as db

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    db.add_user(user_id, username)

    keyboard = [
        [InlineKeyboardButton("Upload File", callback_data="upload")],
        [InlineKeyboardButton("Search Files", callback_data="search")],
        [InlineKeyboardButton("My Subscription", callback_data="my_subscription")],
        [InlineKeyboardButton("Help", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome to BackupThing!\n"
        "Your personal file backup and retrieval system.\n"
        "What would you like to do?",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Available Commands:\n"
        "/start - Show main menu\n"
        "/upload - Instructions for uploading files with tags\n"
        "/search [query] - Initiate a search based on tags, filename, or extension\n"
        "/my_files - List recently uploaded files by the current user\n"
        "/tags - List all unique tags associated with your files\n"
        "/delete [query] - Delete files by name or tag\n"
        "/subscribe - Access subscription plans and payment options\n"
        "/my_subscription - View current subscription status and limits\n"
        "/shared_vaults - (Premium only) Manage shared tagged vaults\n"
        "To upload a file, send it with a caption like: `My important document #work #projectX`"
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    message = update.message
    file_id = None
    file_name = None
    file_type = None
    file_extension = None

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        file_type = message.document.mime_type
        if "." in file_name:
            file_extension = file_name.split(".")[-1].lower()
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = f"photo_{message.date.strftime('%Y%m%d_%H%M%S')}.jpg"
        file_type = "image/jpeg"
        file_extension = "jpg"
    elif message.video:
        file_id = message.video.file_id
        file_name = f"video_{message.date.strftime('%Y%m%d_%H%M%S')}.mp4"
        file_type = "video/mp4"
        file_extension = "mp4"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = (
            message.audio.file_name
            or f"audio_{message.date.strftime('%Y%m%d_%H%M%S')}.mp3"
        )
        file_type = message.audio.mime_type
        if "." in file_name:
            file_extension = file_name.split(".")[-1].lower()
        else:
            file_extension = "mp3"  # Default for audio
    else:
        await message.reply_text(
            "Unsupported file type. Please upload a document, photo, video, or audio."
        )
        return

    caption = message.caption or ""
    tags = [tag.strip() for tag in caption.split("#") if tag.strip()]

    db.add_file(user_id, file_id, file_name, file_extension, file_type, caption, tags)
    db.record_upload(user_id)
    db.record_tag_usage(user_id, len(tags))
    await message.reply_text(f"File '{file_name}' saved with tags: {', '.join(tags)}")


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Free Tier", callback_data="plan_free")],
        [InlineKeyboardButton("Monthly Plan ($5)", callback_data="plan_monthly")],
        [InlineKeyboardButton("Premium Plan ($15)", callback_data="plan_premium")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Choose your subscription plan:", reply_markup=reply_markup
    )


async def precheckout_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload != "backupthing_subscription":
        await query.answer(
            ok=False, error_message="Something went wrong with the payment."
        )
    else:
        await query.answer(ok=True)


async def successful_payment_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    user_id = update.effective_user.id
    payload = update.message.successful_payment.invoice_payload

    if payload == "backupthing_subscription":
        # Extract plan from context or payload if needed
        # For now, assuming a simple mapping or passing plan in payload
        plan_name = (
            "monthly"  # This needs to be dynamic based on which plan was purchased
        )
        db.update_user_subscription(user_id, plan_name)
        await update.message.reply_text(
            "Payment successful! Your subscription has been activated."
        )
    else:
        await update.message.reply_text(
            "Payment successful, but couldn't determine subscription plan."
        )


async def my_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if user:
        plan = user[2]  # Assuming subscription_plan is the 3rd column
        await update.message.reply_text(
            f"Your current subscription plan: {plan.capitalize()}"
        )
    else:
        await update.message.reply_text(
            "Could not retrieve your subscription information."
        )


async def shared_vaults(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if user and user[2] == "premium":  # Assuming subscription_plan is the 3rd column
        await update.message.reply_text(
            "Welcome to Shared Vaults! (Feature under development)"
        )
    else:
        await update.message.reply_text(
            "This feature is only available for Premium subscribers."
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "upload":
        await query.edit_message_text(
            "To upload a file, send it with a caption like: `My important document #work #projectX`"
        )
    elif data == "search":
        await query.edit_message_text(
            "To search for files, simply type your query (e.g., `report.pdf`, `#meeting`, `image #vacation`)."
        )
    elif data == "my_subscription":
        await my_subscription(query, context)
    elif data == "help":
        await help_command(query, context)
    elif data.startswith("plan_"):
        plan = data.split("_")[1]
        if plan == "free":
            await query.edit_message_text(
                "You are on the Free Tier. Upgrade for more features!"
            )
        else:
            title = f"{plan.capitalize()} Plan"
            description = f"Access to {plan} features of BackupThing Bot."
            payload = "backupthing_subscription"
            currency = "USD"
            price = 0
            if plan == "monthly":
                price = 500  # $5.00 in cents
            elif plan == "premium":
                price = 1500  # $15.00 in cents

            prices = [LabeledPrice(label=title, amount=price)]

            await context.bot.send_invoice(
                chat_id=query.message.chat_id,
                title=title,
                description=description,
                payload=payload,
                provider_token=TELEGRAM_PAYMENTS_PROVIDER_TOKEN,
                currency=currency,
                prices=prices,
                start_parameter="backupthing-subscription",
                photo_url="https://via.placeholder.com/200",  # Placeholder image
                photo_width=200,
                photo_height=200,
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                send_email_to_provider=False,
                send_phone_number_to_provider=False,
                is_flexible=False,
                disable_notification=False,
                reply_to_message_id=None,
                parse_mode=None,
                reply_markup=None,
            )


def main() -> None:
    """Start the bot."""
    db.init_db()
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tags", list_tags))
    application.add_handler(CommandHandler("recent", recent_files))
    application.add_handler(CommandHandler("delete", delete_file))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("my_subscription", my_subscription))
    application.add_handler(CommandHandler("shared_vaults", shared_vaults))

    # Message Handlers
    application.add_handler(
        MessageHandler(
            filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
            handle_file,
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, search_files)
    )

    # Payment Handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback)
    )

    # Callback Query Handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Run the bot
    application.run_polling()


if __name__ == "__main__":
    main()

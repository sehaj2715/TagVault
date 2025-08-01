import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from config import TELEGRAM_TOKEN
import database as db

# Enable logging for the bot
# This helps in debugging and monitoring the bot's activity
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /start command.
    Welcomes the user, adds them to the database if they are new,
    and presents an inline keyboard with main options.
    """
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    db.add_user(user_id, username)  # Add user to the database if not already present

    # Define inline keyboard buttons for main actions
    keyboard = [
        [InlineKeyboardButton("Upload File", callback_data="upload")],
        [InlineKeyboardButton("Search Files", callback_data="search")],
        [InlineKeyboardButton("Help", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send welcome message with the inline keyboard
    await update.message.reply_text(
        "Welcome to BackupThing!\n"
        "Your personal file backup and retrieval system.\n"
        "What would you like to do?",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /help command.
    Provides a list of available commands and their usage.
    """
    await update.message.reply_text(
        "Available Commands:\n"
        "/start - Show main menu\n"
        "/upload - Instructions for uploading files with tags\n"
        "/search [query] - Initiate a search based on tags, filename, or extension\n"
        "/files - List recently uploaded files by the current user\n"
        "/tags - List all unique tags associated with your files\n"
        "/delete [query] - Delete files by name or tag\n"
        "/edit <file_query> [name:new_name] [tags:[add|remove|set] tag1 tag2 ...] - Edit file name and/or tags\n"
        "To upload a file, send it with a caption like: `My important document #work projectX`"
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles incoming files (documents, photos, videos, audio).
    Extracts file information, parses caption for file name and tags,
    stores metadata in the database, and records user activity.
    """
    user_id = update.effective_user.id
    message = update.message
    file_id = None
    file_name = None
    file_type = None
    file_extension = None

    # Stores the Telegram-specific category (document, photo, video, audio)
    # This is crucial for sending the file back using the correct Telegram API method.
    telegram_file_category = None

    # Determine file type and extract relevant information
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        file_type = message.document.mime_type
        telegram_file_category = "document"
        if "." in file_name:
            file_extension = file_name.split(".")[-1].lower()
    elif message.photo:
        # For photos, Telegram provides multiple sizes; we take the largest one
        file_id = message.photo[-1].file_id
        file_name = f"photo_{message.date.strftime('%Y%m%d_%H%M%S')}.jpg"
        file_type = "image/jpeg"
        telegram_file_category = "photo"
        file_extension = "jpg"
    elif message.video:
        file_id = message.video.file_id
        file_name = f"video_{message.date.strftime('%Y%m%d_%H%M%S')}.mp4"
        file_type = "video/mp4"
        telegram_file_category = "video"
        file_extension = "mp4"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = (
            message.audio.file_name
            or f"audio_{message.date.strftime('%Y%m%d_%H%M%S')}.mp3"
        )
        file_type = message.audio.mime_type
        telegram_file_category = "audio"
        if "." in file_name:
            file_extension = file_name.split(".")[-1].lower()
        else:
            file_extension = "mp3"  # Default for audio if no extension in name
    else:
        # Reply if the uploaded file type is not supported
        await message.reply_text(
            "Unsupported file type. Please upload a document, photo, video, or audio."
        )
        return

    caption = message.caption or ""
    
    # Split caption into potential file name and tags.
    # The part before the first '#' is considered the user-provided file name.
    caption_parts = caption.split("#", 1)
    user_provided_name = caption_parts[0].strip()
    
    # If a user-provided name exists, use it; otherwise, keep the default file_name
    if user_provided_name:
        file_name = user_provided_name
    
    tags = []
    # If there's a part after '#', extract tags from it
    if len(caption_parts) > 1:
        # Tags are now space-separated after the first '#'
        tags = [tag.strip() for tag in caption_parts[1].split() if tag.strip()]

    # Add file metadata to the database
    db.add_file(user_id, file_id, file_name, file_extension, file_type, telegram_file_category, caption, tags)
    db.record_upload(user_id)  # Record the upload for user statistics
    db.record_tag_usage(user_id, len(tags))  # Record tag usage
    
    # Confirm file saving to the user
    await message.reply_text(f"File '{file_name}' saved with tags: {', '.join(tags)}")


async def list_tags(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /tags command.
    Retrieves and displays all unique tags associated with the user's files.
    """
    user_id = update.effective_user.id
    tags = db.get_all_tags(user_id)  # Fetch all unique tags for the user
    if tags:
        await update.message.reply_text(f"Your tags: {', '.join(tags)}")
    else:
        await update.message.reply_text("You haven't used any tags yet.")


PAGE_SIZE = 5 # Number of files to display per page

async def files_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /files command (formerly /my_files).
    Displays a paginated list of recently uploaded files by the current user, including their tags.
    """
    user_id = update.effective_user.id
    offset = context.args[0] if context.args and context.args[0].isdigit() else 0
    offset = int(offset)

    files = db.get_recent_files(user_id, limit=PAGE_SIZE, offset=offset)  # Fetch recent files from the database with pagination
    
    if files:
        await update.message.reply_text(f"Your recent files (Page {offset // PAGE_SIZE + 1}):")
        # Iterate through files and send them back to the user
        for file_id, file_name, file_type, telegram_file_category, _, tags_str in files:
            caption_text = file_name
            if tags_str:
                # Display tags concisely within parentheses
                caption_text += f" ({tags_str.replace(', ', ', ')})"

            # Use the stored telegram_file_category to send the file correctly
            if telegram_file_category == "photo":
                await update.message.reply_photo(file_id, caption=caption_text)
            elif telegram_file_category == "video":
                await update.message.reply_video(file_id, caption=caption_text)
            elif telegram_file_category == "audio":
                await update.message.reply_audio(file_id, caption=caption_text)
            elif telegram_file_category == "document":
                await update.message.reply_document(file_id, caption=caption_text)
            else:
                # Fallback for older entries or unknown types based on MIME type
                if file_type.startswith("image"):
                    await update.message.reply_photo(file_id, caption=caption_text)
                elif file_type.startswith("video"):
                    await update.message.reply_video(file_id, caption=caption_text)
                elif file_type.startswith("audio"):
                    await update.message.reply_audio(file_id, caption=caption_text)
                else:
                    await update.message.reply_document(file_id, caption=caption_text)
        
        # Add pagination buttons
        keyboard = []
        if offset > 0:
            keyboard.append(InlineKeyboardButton("Previous", callback_data=f"files_page_{offset - PAGE_SIZE}"))
        if len(files) == PAGE_SIZE:
            keyboard.append(InlineKeyboardButton("Next", callback_data=f"files_page_{offset + PAGE_SIZE}"))
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup([keyboard])
            await update.message.reply_text("", reply_markup=reply_markup)

    else:
        await update.message.reply_text("You haven't uploaded any files recently.")


async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /delete command.
    First, lists files matching the query and asks for user confirmation before deleting.
    """
    user_id = update.effective_user.id
    query = " ".join(context.args)  # Get the query from command arguments
    if not query:
        await update.message.reply_text(
            "Please provide a file name or tag to delete. E.g., `/delete report.pdf` or `/delete #old`"
        )
        return

    # Find files matching the query
    files_to_delete = db.find_files(user_id, query)

    if not files_to_delete:
        await update.message.reply_text(f"No files found matching '{query}'.")
        return

    # Prepare message listing files to be deleted
    file_list_message = "The following files will be deleted:\n"
    for file_id, file_name, file_type, telegram_file_category, _, tags_str in files_to_delete:
        file_list_message += f"- {file_name} ({file_type})\n"

    context.user_data['delete_query'] = query # Store the query for confirmation

    # Create inline keyboard for confirmation
    keyboard = [
        [InlineKeyboardButton("Confirm Delete", callback_data="confirm_delete_action")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_delete")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send confirmation message
    await update.message.reply_text(
        file_list_message + "\nAre you sure you want to delete these files?",
        reply_markup=reply_markup,
    )


async def edit_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /edit command.
    Allows users to edit a file's name and/or its tags (add, remove, or set).
    Usage: /edit <file_query> [name:new_name] [tags:[add|remove|set] tag1 tag2 ...]
    """
    user_id = update.effective_user.id
    args = context.args  # Get arguments after the /edit command
    if not args:
        await update.message.reply_text(
            "Please provide a file query and what to edit. "
            "Usage: `/edit <file_query> [name:new_name] [tags:[add|remove|set] tag1 tag2 ...]`"
        )
        return

    file_query_parts = []
    new_name = None
    new_tags_str = None
    tag_operation = None # Can be 'add', 'remove', 'set'

    # Parse arguments to extract file query, new name, and tag operation
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.lower().startswith("name:"):
            new_name = arg[len("name:"):]
            i += 1
        elif arg.lower().startswith("tags:"):
            tag_operation_str = arg[len("tags:"):]
            # Check if a specific tag operation (add, remove, set) is provided
            if tag_operation_str in ["add", "remove", "set"]:
                tag_operation = tag_operation_str
                new_tags_str = []
                i += 1 # Move to the next argument which should be the first tag
                # Collect all subsequent arguments as tags until another command argument is found
                while i < len(args) and not (args[i].lower().startswith("name:") or args[i].lower().startswith("tags:")):
                    new_tags_str.append(args[i])
                    i += 1
                new_tags_str = " ".join(new_tags_str)
            else: 
                # If no explicit operation, default to 'set' and treat the current arg as the first tag
                tag_operation = "set"
                new_tags_str = []
                new_tags_str.append(tag_operation_str) # First tag
                i += 1
                while i < len(args) and not (args[i].lower().startswith("name:") or args[i].lower().startswith("tags:")):
                    new_tags_str.append(args[i])
                    i += 1
                new_tags_str = " ".join(new_tags_str)
        else:
            file_query_parts.append(arg)
            i += 1
    
    file_query = " ".join(file_query_parts) # Reconstruct the file query

    # Validate input
    if not file_query:
        await update.message.reply_text(
            "Please provide a file query. "
            "Usage: `/edit <file_query> [name:new_name] [tags:[add|remove|set] tag1 tag2 ...]`"
        )
        return

    if new_name is None and new_tags_str is None:
        await update.message.reply_text(
            "Please provide either a new name or new tags to update. "
            "Usage: `/edit <file_query> [name:new_name] [tags:[add|remove|set] tag1 tag2 ...]`"
        )
        return

    # Find files matching the query
    files = db.find_files(user_id, file_query)

    if not files:
        await update.message.reply_text(f"No files found matching '{file_query}'.")
        return
    elif len(files) > 1:
        # If multiple files match, ask user to be more specific
        file_list = "\n".join([f"- {f[1]} ({f[2]})" for f in files])
        await update.message.reply_text(
            f"Multiple files found matching '{file_query}':\n{file_list}\n"
            "Please be more specific with your query to edit a single file."
        )
        return
    
    # If only one file is found, proceed with the update
    file_id_to_update = files[0][0]
    current_file_name = files[0][1]
    
    updated_tags = None
    if new_tags_str is not None:
        updated_tags = [tag.strip() for tag in new_tags_str.split() if tag.strip()]

    # Call the database function to update file metadata
    rows_updated = db.update_file_metadata(user_id, file_id_to_update, new_name, updated_tags, tag_operation)

    if rows_updated > 0:
        response_message = f"Successfully updated file '{current_file_name}'."
        if new_name:
            response_message += f" New name: '{new_name}'."
        if updated_tags is not None:
            response_message += f" New tags: {', '.join(updated_tags)}."
        await update.message.reply_text(response_message)
    else:
        await update.message.reply_text(f"Failed to update file '{current_file_name}'.")


async def search_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles text messages that are not commands.
    Performs a search for files based on the user's text query (filename, extension, or tags).
    Displays matching files, including their tags with pagination.
    """
    user_id = update.effective_user.id
    query = update.message.text # The entire text message is the search query
    
    # Store the query for pagination callbacks
    context.user_data['last_search_query'] = query
    
    offset = 0 # Initial offset for search
    if context.args and context.args[0].isdigit(): # Check if offset is provided in args (for callback)
        offset = int(context.args[0])

    if not query:
        await update.message.reply_text(
            "Please provide a search query. E.g., `report.pdf`, `#meeting`, `image #vacation`"
        )
        return

    files = db.find_files(user_id, query, limit=PAGE_SIZE, offset=offset) # Find files in the database with pagination

    if files:
        await update.message.reply_text(f"Files matching '{query}' (Page {offset // PAGE_SIZE + 1}):")
        # Iterate through files and send them back to the user
        for file_id, file_name, file_type, telegram_file_category, _, tags_str in files:
            caption_text = file_name
            if tags_str:
                # Display tags concisely within parentheses
                caption_text += f" ({tags_str.replace(', ', ', ')})"

            # Use the stored telegram_file_category to send the file correctly
            if telegram_file_category == "photo":
                await update.message.reply_photo(file_id, caption=caption_text)
            elif telegram_file_category == "video":
                await update.message.reply_video(file_id, caption=caption_text)
            elif telegram_file_category == "audio":
                await update.message.reply_audio(file_id, caption=caption_text)
            elif telegram_file_category == "document":
                await update.message.reply_document(file_id, caption=caption_text)
            else:
                # Fallback for older entries or unknown types based on MIME type
                if file_type.startswith("image"):
                    await update.message.reply_photo(file_id, caption=caption_text)
                elif file_type.startswith("video"):
                    await update.message.reply_video(file_id, caption=caption_text)
                elif file_type.startswith("audio"):
                    await update.message.reply_audio(file_id, caption=caption_text)
                else:
                    await update.message.reply_document(file_id, caption=caption_text)
        
        # Add pagination buttons
        keyboard = []
        if offset > 0:
            keyboard.append(InlineKeyboardButton("Previous", callback_data=f"search_page_{offset - PAGE_SIZE}"))
        if len(files) == PAGE_SIZE:
            keyboard.append(InlineKeyboardButton("Next", callback_data=f"search_page_{offset + PAGE_SIZE}"))
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup([keyboard])
            await update.message.reply_text("", reply_markup=reply_markup)

    else:
        await update.message.reply_text(f"No files found matching '{query}'.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles inline keyboard button presses.
    Directs actions based on the callback_data from the pressed button.
    """
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query
    data = query.data # Get the data associated with the button

    if data == "upload":
        await query.edit_message_text(
            "To upload a file, send it with a caption like: `My important document #work projectX`"
        )
    elif data == "search":
        await query.edit_message_text(
            "To search for files, simply type your query (e.g., `report.pdf`, `#meeting`, `image #vacation`)."
        )
    elif data == "help":
        await help_command(update, context) # Call the help command handler
    elif data == "confirm_delete_action": # Corrected to use the simple action string
        user_id = update.effective_user.id
        original_query = context.user_data.get('delete_query') # Retrieve query from user_data
        if not original_query:
            await query.edit_message_text("Error: No delete query found. Please try again.")
            return
        rows_deleted = db.delete_files(user_id, original_query) # Perform the deletion
        if rows_deleted > 0:
            await query.edit_message_text(f"Deleted {rows_deleted} file(s) matching '{original_query}'.")
        else:
            await query.edit_message_text(f"No files were deleted for query '{original_query}'.")
    elif data == "cancel_delete":
        await query.edit_message_text("File deletion cancelled.")
    elif data.startswith("files_page_"):
        user_id = update.effective_user.id
        offset = int(data.replace("files_page_", ""))
        files = db.get_recent_files(user_id, limit=PAGE_SIZE, offset=offset)
        
        if files:
            message_text = f"Your recent files (Page {offset // PAGE_SIZE + 1}):\n"
            for file_id, file_name, file_type, telegram_file_category, _, tags_str in files:
                caption_text = file_name
                if tags_str:
                    caption_text += f" ({tags_str.replace(', ', ', ')})"
                message_text += f"- {caption_text}\n"

            keyboard = []
            if offset > 0:
                keyboard.append(InlineKeyboardButton("Previous", callback_data=f"files_page_{offset - PAGE_SIZE}"))
            if len(files) == PAGE_SIZE:
                keyboard.append(InlineKeyboardButton("Next", callback_data=f"files_page_{offset + PAGE_SIZE}"))
            
            reply_markup = InlineKeyboardMarkup([keyboard])
            await query.edit_message_text(message_text, reply_markup=reply_markup)
        else:
            await query.edit_message_text("No more files.")

    elif data.startswith("search_page_"):
        user_id = update.effective_user.id
        offset = int(data.replace("search_page_", ""))
        query_text = context.user_data.get('last_search_query')

        if not query_text:
            await query.edit_message_text("No search query found. Please start a new search.")
            return

        files = db.find_files(user_id, query_text, limit=PAGE_SIZE, offset=offset)

        if files:
            message_text = f"Files matching '{query_text}' (Page {offset // PAGE_SIZE + 1}):\n"
            for file_id, file_name, file_type, telegram_file_category, _, tags_str in files:
                caption_text = file_name
                if tags_str:
                    caption_text += f" ({tags_str.replace(', ', ', ')})"
                message_text += f"- {caption_text}\n"

            keyboard = []
            if offset > 0:
                keyboard.append(InlineKeyboardButton("Previous", callback_data=f"search_page_{offset - PAGE_SIZE}"))
            if len(files) == PAGE_SIZE:
                keyboard.append(InlineKeyboardButton("Next", callback_data=f"search_page_{offset + PAGE_SIZE}"))
            
            reply_markup = InlineKeyboardMarkup([keyboard])
            await query.edit_message_text(message_text, reply_markup=reply_markup)
        else:
            await query.edit_message_text("No more files for this search.")


from web_server import start_web_server_thread

def main() -> None:
    """
    Main function to set up and run the Telegram bot.
    Initializes the database and registers all command and message handlers.
    """
    db.init_db()  # Initialize the SQLite database
    
    # Start the web server in a separate thread
    start_web_server_thread()

    # Create the Application and pass your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tags", list_tags))
    application.add_handler(CommandHandler("files", files_command)) # Renamed from my_files
    application.add_handler(CommandHandler("delete", delete_file))
    application.add_handler(CommandHandler("edit", edit_file))
    

    # Register message handlers
    # Handles incoming files (documents, photos, videos, audio)
    application.add_handler(
        MessageHandler(
            filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
            handle_file,
        )
    )
    # Handles all other text messages as search queries (excluding commands)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, search_files)
    )

    
    # Register callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    # Entry point for the script
    main()
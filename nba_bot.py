import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import requests
import json
from datetime import datetime, timedelta
import os
import pytz

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# NBA API configuration
NBA_API_URL = "https://api.balldontlie.io/v1"
API_KEY = "c0b642c0-00be-446a-a50c-90a4b328839f"  # You should get a free API key from balldontlie.io
HEADERS = {
    "Authorization": f"{API_KEY}",
    "Content-Type": "application/json"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"Hi {user.first_name}! I'm your NBA Statistics Bot. 🏀\n\n"
        "Use /games to see completed NBA games and statistics.\n"
        "Use /teams to see NBA team statistics.\n"
        "Use /players to search for player statistics."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "NBA Statistics Bot Help:\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/games - Show completed NBA games from the most recent game day\n"
        "/teams - Show NBA team statistics\n"
        "/players - Search for player statistics\n\n"
        "Note: You need a valid NBA API key for full functionality."
    )

async def games_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show completed NBA games from the most recent game day."""
    await update.message.reply_text("🔍 Fetching completed NBA games...")

    try:
        # Function to find the most recent day with completed games
        def find_recent_game_day():
            # Try up to 7 days back to find a day with completed games
            for days_back in range(1, 8):
                test_date = datetime.now() - timedelta(days=days_back)
                game_date = test_date.strftime("%Y-%m-%d")

                games_url = f"{NBA_API_URL}/games"
                params = {
                    "dates[]": game_date,
                    "per_page": 100
                }
                response = requests.get(games_url, headers=HEADERS, params=params)

                if response.status_code == 200:
                    games_data = response.json().get('data', [])
                    # Look for completed games (status = "Final")
                    completed_games = [game for game in games_data if game.get('status') == 'Final']
                    if completed_games:
                        return game_date, completed_games

            # If no completed games found in the last 7 days, return yesterday
            return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"), []

        # Find the most recent game day with completed games
        game_date, games_data = find_recent_game_day()

        if not games_data:
            await update.message.reply_text("No completed NBA games found in the last 7 days.")
            return

        # Create a summary of completed games
        message = f"🏀 Completed NBA Games for {game_date} 🏀\n\n"

        completed_count = 0
        for game in games_data:  # Show ALL completed games
            home_team = game['home_team']['full_name']
            visitor_team = game['visitor_team']['full_name']
            home_score = game['home_team_score']
            visitor_score = game['visitor_team_score']
            status = game['status']

            # Only show completed games with final scores
            if status == "Final":
                result = f"{home_team} {home_score} - {visitor_score} {visitor_team}"
                message += f"🔹 {result}\n"
                completed_count += 1

        if completed_count == 0:
            await update.message.reply_text(f"No completed games found for {game_date}.")
            return

        # Create buttons for each game to allow individual selection
        keyboard = []
        game_index = 0
        for game in games_data:
            if game.get('status') == 'Final':
                home_team = game['home_team']['full_name']
                visitor_team = game['visitor_team']['full_name']
                # Create a button for each game with unique callback data
                callback_data = f"game_details_{game_date}_{game_index}"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{visitor_team} @ {home_team}",
                        callback_data=callback_data
                    )
                ])
                game_index += 1

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(message, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in games_command: {e}")
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")

async def teams_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show NBA team statistics."""
    await update.message.reply_text("🔍 Fetching NBA team statistics...")

    try:
        # Fetch all teams
        teams_url = f"{NBA_API_URL}/teams"
        params = {"per_page": 30}
        response = requests.get(teams_url, headers=HEADERS, params=params)

        if response.status_code == 200:
            teams_data = response.json().get('data', [])

            if not teams_data:
                await update.message.reply_text("No team data available.")
                return

            # Show top teams by conference
            message = "🏀 NBA Team Statistics 🏀\n\n"

            # Group teams by conference
            eastern_teams = [t for t in teams_data if t['conference'] == 'East']
            western_teams = [t for t in teams_data if t['conference'] == 'West']

            message += "🌅 Eastern Conference Top Teams:\n"
            for team in eastern_teams[:5]:
                message += f"🔹 {team['full_name']} ({team['abbreviation']})\n"

            message += "\n🌇 Western Conference Top Teams:\n"
            for team in western_teams[:5]:
                message += f"🔹 {team['full_name']} ({team['abbreviation']})\n"

            await update.message.reply_text(message)
        else:
            await update.message.reply_text(f"❌ Error fetching teams: {response.status_code}")

    except Exception as e:
        logger.error(f"Error in teams_command: {e}")
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")

async def players_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for player statistics."""
    await update.message.reply_text("🔍 Please enter a player name to search for:")

    # Store the context for the next message
    context.user_data['awaiting_player_name'] = True

async def handle_player_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the player name input and search for statistics."""
    if context.user_data.get('awaiting_player_name'):
        player_name = update.message.text
        context.user_data['awaiting_player_name'] = False

        await update.message.reply_text(f"🔍 Searching for player: {player_name}...")

        try:
            # Search for players by name
            players_url = f"{NBA_API_URL}/players"
            params = {
                "search": player_name,
                "per_page": 10
            }
            response = requests.get(players_url, headers=HEADERS, params=params)

            if response.status_code == 200:
                players_data = response.json().get('data', [])

                if not players_data:
                    await update.message.reply_text(f"No players found with name: {player_name}")
                    return

                # Show player information
                message = f"🏀 Player Search Results for '{player_name}' 🏀\n\n"

                for player in players_data[:5]:  # Show first 5 results
                    message += (
                        f"🔹 {player['first_name']} {player['last_name']}\n"
                        f"   Team: {player['team']['full_name']}\n"
                        f"   Position: {player['position']}\n"
                        f"   Height: {player['height_feet']}'{player['height_inches']}\"\n"
                        f"   Weight: {player['weight_pounds']} lbs\n\n"
                    )

                await update.message.reply_text(message)
            else:
                await update.message.reply_text(f"❌ Error searching for players: {response.status_code}")

        except Exception as e:
            logger.error(f"Error in player search: {e}")
            await update.message.reply_text(f"❌ An error occurred: {str(e)}")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button click events."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data.startswith("game_details_"):
        # Parse the callback data: game_details_{date}_{game_index}
        parts = callback_data.split('_')
        if len(parts) >= 4:
            date = parts[2]
            game_index = int(parts[3])
            await show_game_details(query, date, game_index)
        else:
            # Backward compatibility for old format
            date = callback_data.replace("game_details_", "")
            await show_game_details(query, date, 0)

async def show_game_details(query, date, game_index=0):
    """Show detailed game statistics for a specific game."""
    try:
        # Fetch games for the specific date
        games_url = f"{NBA_API_URL}/games"
        params = {
            "dates[]": date,
            "per_page": 100
        }
        response = requests.get(games_url, headers=HEADERS, params=params)

        if response.status_code == 200:
            games_data = response.json().get('data', [])

            if not games_data:
                await query.edit_message_text("No game details available for this date.")
                return

            # Show detailed statistics for the selected game
            completed_games = [game for game in games_data if game.get('status') == 'Final']
            if not completed_games:
                await query.edit_message_text(f"No completed games found for {date}.")
                return

            # Ensure game_index is within valid range
            if game_index >= len(completed_games):
                game_index = 0

            game = completed_games[game_index]
            home_team = game['home_team']['full_name']
            visitor_team = game['visitor_team']['full_name']
            home_score = game['home_team_score']
            visitor_score = game['visitor_team_score']

            # Extract additional game details
            game_date = game.get('date', 'N/A')
            season = game.get('season', 'N/A')
            game_time = game.get('time', 'N/A')
            postseason = "Yes" if game.get('postseason') else "No"

            # Extract quarter scores if available
            home_q1 = game.get('home_q1', 0)
            home_q2 = game.get('home_q2', 0)
            home_q3 = game.get('home_q3', 0)
            home_q4 = game.get('home_q4', 0)
            visitor_q1 = game.get('visitor_q1', 0)
            visitor_q2 = game.get('visitor_q2', 0)
            visitor_q3 = game.get('visitor_q3', 0)
            visitor_q4 = game.get('visitor_q4', 0)

            # Create focused game statistics message with only requested stats
            message = f"🏀 GAME STATISTICS: {visitor_team} @ {home_team} 🏀\n\n"

            # Quarter-by-quarter scores
            if any([home_q1, home_q2, home_q3, home_q4, visitor_q1, visitor_q2, visitor_q3, visitor_q4]):
                message += "📊 QUARTER SCORES:\n"
                message += f"Q1: {visitor_team} {visitor_q1} - {home_q1} {home_team}\n"
                message += f"Q2: {visitor_team} {visitor_q2} - {home_q2} {home_team}\n"
                message += f"Q3: {visitor_team} {visitor_q3} - {home_q3} {home_team}\n"
                message += f"Q4: {visitor_team} {visitor_q4} - {home_q4} {home_team}\n\n"

            # Final score
            message += "🔢 FINAL SCORE:\n"
            message += f"{visitor_team}: {visitor_score}\n"
            message += f"{home_team}: {home_score}\n\n"

            # Try to get player statistics (may not be available with current API key)
            try:
                stats_url = f"{NBA_API_URL}/stats"
                stats_params = {
                    "game_ids[]": game.get('id'),
                    "per_page": 100
                }
                stats_response = requests.get(stats_url, headers=HEADERS, params=stats_params)

                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    if 'data' in stats_data and stats_data['data']:
                        stats = stats_data['data']

                        # Calculate team totals
                        home_stats = {
                            'pts': sum(s.get('pts', 0) for s in stats if s.get('team', {}).get('id') == game['home_team']['id']),
                            'reb': sum(s.get('reb', 0) for s in stats if s.get('team', {}).get('id') == game['home_team']['id']),
                            'ast': sum(s.get('ast', 0) for s in stats if s.get('team', {}).get('id') == game['home_team']['id']),
                            'stl': sum(s.get('stl', 0) for s in stats if s.get('team', {}).get('id') == game['home_team']['id'])
                        }

                        visitor_stats = {
                            'pts': sum(s.get('pts', 0) for s in stats if s.get('team', {}).get('id') == game['visitor_team']['id']),
                            'reb': sum(s.get('reb', 0) for s in stats if s.get('team', {}).get('id') == game['visitor_team']['id']),
                            'ast': sum(s.get('ast', 0) for s in stats if s.get('team', {}).get('id') == game['visitor_team']['id']),
                            'stl': sum(s.get('stl', 0) for s in stats if s.get('team', {}).get('id') == game['visitor_team']['id'])
                        }

                        # Team statistics
                        message += "📊 TEAM STATISTICS:\n"
                        message += f"{home_team}: {home_stats['pts']} PTS, {home_stats['reb']} REB, {home_stats['ast']} AST, {home_stats['stl']} STL\n"
                        message += f"{visitor_team}: {visitor_stats['pts']} PTS, {visitor_stats['reb']} REB, {visitor_stats['ast']} AST, {visitor_stats['stl']} STL\n\n"

                        # Top 3 players
                        top_players = sorted(stats, key=lambda x: x.get('pts', 0), reverse=True)[:3]
                        message += "🌟 TOP 3 PLAYERS:\n"
                        for i, player in enumerate(top_players, 1):
                            p_name = f"{player.get('player', {}).get('first_name', 'Unknown')} {player.get('player', {}).get('last_name', 'Player')}"
                            team_name = player.get('team', {}).get('abbreviation', 'TEAM')
                            pts = player.get('pts', 0)
                            reb = player.get('reb', 0)
                            ast = player.get('ast', 0)
                            stl = player.get('stl', 0)
                            message += f"{i}. {p_name} ({team_name}): {pts} PTS, {reb} REB, {ast} AST, {stl} STL\n"
                    else:
                        message += "⚠️ Player statistics not available for this game\n\n"
                else:
                    message += "⚠️ Player statistics require premium API access\n\n"
            except Exception as e:
                message += f"⚠️ Error fetching player stats: {str(e)}\n\n"

            message += "💡 Note: Quarter scores are available. For full player statistics, a premium NBA API key is required."

            await query.edit_message_text(message)
        else:
            await query.edit_message_text(f"❌ Error fetching game details: {response.status_code}")

    except Exception as e:
        logger.error(f"Error in game details: {e}")
        await query.edit_message_text(f"❌ An error occurred: {str(e)}")

def main() -> None:
    """Start the bot."""
    # Fix for timezone issue with apscheduler
    try:
        # Try to set a valid timezone
        from apscheduler.schedulers.base import get_localzone
        # Force use of pytz timezone
        import pytz
        local_tz = pytz.timezone('Europe/Moscow')  # Using user's timezone
        os.environ['TZ'] = 'Europe/Moscow'

        # Create the Application and pass it your bot's token.
        # Get your bot token from @BotFather on Telegram
        application = Application.builder().token("8090701467:AAEPNzhgfeT4Bd6KYSZN4VMcSVSsz3vm3-Q").build()
    except Exception as e:
        logger.error(f"Error initializing bot: {e}")
        print(f"Error initializing bot: {e}")
        print("Please make sure you have the latest versions of all dependencies:")
        print("pip install --upgrade python-telegram-bot pytz apscheduler")
        return

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("games", games_command))
    application.add_handler(CommandHandler("teams", teams_command))
    application.add_handler(CommandHandler("players", players_command))

    # Add message handler for player search
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_player_search))

    # Add callback query handler for buttons
    application.add_handler(CallbackQueryHandler(button_click))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
"""
Discord bot for coordinating pen-and-paper-shenanigans
"""
import random
import logging
from datetime import time
from datetime import datetime
import asyncio
import psycopg2
import discord
from discord import app_commands
from discord.ext import commands
from paps_bot.database import create_connection, create_table_sql

"""
Bot shutdown state for graceful shutdown of bot.
"""
IS_SHUTTING_DOWN = False


# create the bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="$", intents=intents)
# get the bot logger
logger = logging.getLogger("discord")


def format_date(date_str, format_str):
    """Function to format EU date formats DD-MM-YYYY to SQL accepted time object"""
    try:
        logger.info("Attempting to format time: %s", date_str)
        date_obj = datetime.strptime(date_str, format_str)
        logger.info("Time successfully formatted: %s", date_obj.date())
        return date_obj.date()
    except ValueError as err:
        logger.error("Time formatting error detected: \n %s", err)
        return None


@bot.event
async def on_ready():
    """Executed when the bot joins the discord server"""
    logger.info("We have logged in as %s", bot.user)
    logger.info("Creating table, if it does not exist already.")
    # Create table, if it does not already exist
    create_table_sql()
    try:
        synced = await bot.tree.sync()
        logger.info("synced %s command(s)" % (len(synced)))
    except psycopg2.DatabaseError as err:
        logger.error("An error has occured:\n %s", err)
    logger.info("========= Ready! =========")


@bot.event
async def on_shutdown():
    """Event handler on_shutdown listens for sigterm signals, and performs an action."""
    global IS_SHUTTING_DOWN
    IS_SHUTTING_DOWN = True
    logger.warning("Bot is shutting down...")
    conn = create_connection()
    conn.rollback()
    conn.close()
    await bot.logout()
    await bot.close()


@bot.event
async def on_guild_join():
    """Once a guild is joined, initiate the db if it does not already exist."""
    logger.info("Establishing connection to postgreSQL databse ...")
    conn = create_connection()
    logger.info("Creating new table...")
    create_table_sql()
    logger.info("Done, now ready!")
    conn.close()


@bot.command()
async def bot_shutdown(ctx):
    """Just a command that can be executed to notify users that bot is shutting down."""
    if IS_SHUTTING_DOWN:
        await ctx.send("The bot is currently shutting down...")
        return


@bot.tree.command(name="hello", description="Answers with an appropriate hello message")
async def hello(Interaction: discord.Interaction):
    """Funny function to say hello in various ways"""
    options = [
        f"Ahoy {Interaction.user.mention}!",
        f"Hello there, Choom {Interaction.user.mention}!",
        f"Sup,  {Interaction.user.mention}?",
        f"Good day to you, {Interaction.user.mention}!",
        f"Hooooi {Interaction.user.mention}!",
        f"{Interaction.user.mention}, Wha chu want?!",
        f"Howdy, {Interaction.user.mention}!",
    ]

    response = random.choice(options)
    logger.info("Sending message %s ...", response)
    await Interaction.response.send_message(response)


@bot.tree.command(
    name="make-event-novote",
    description="Create an event using the given parameters, voiding the voting process.",
)
@app_commands.describe(
    game_type="Type of event - CPR or DND",
    game_date="Date of event - DD-MM-YYYY",
    game_time="Time of event - HH:MM",
)
async def make_event_novote(
    Interaction: discord.Interaction, game_type: str, game_date: str, game_time: str
):
    """Bot command to insert a new event into paps_table table, voiding vote process."""
    try:
        logger.info(
            "\n============= Forced make-event command executed from discord! NO VOTE WILL BE MADE! =============\n Data received:\n %s \nType: %s, Date: %s, TIME: %s",
            Interaction.user,
            game_type,
            game_type,
            game_time,
        )
        # Some formatting of game_time, we will never set an event to a specific second
        # So in order for SQL to accept just HH:MM we need to add it to whatever is input
        logger.info("Formatting game time to SQL acceptable HH:MM:SS format")
        game_time = game_time + ":00"  # Required, add seconds as 00 to query
        game_time = time.fromisoformat(
            game_time
        )  # Convert above to time object to insert to query.
        game_date = format_date(
            game_date, "%d-%m-%Y"
        )  # Formart EU standard date format to SQL date format.

        logger.info("Establishing connection to database...")
        conn = create_connection()
        cur = conn.cursor()
        logger.info("Connection established, cursor created...")

        logger.info("Sending SQL query to database...")
        cur.execute(
            f"""INSERT INTO paps_table (game_type, game_date, game_time) VALUES ('{game_type}', '{game_date}', '{game_time}')"""
        )

        logger.info(
            "Attempting to add event to paps_table:\n Type: %s, Date: %s, Time: %s",
            game_type,
            game_date,
            game_time,
        )
        conn.commit()
        cur.close()
        conn.close()
        embed = discord.Embed(
            title="Event created WITHOUT a vote", color=discord.Color.red()
        )
        embed.set_author(name=Interaction.user, icon_url=Interaction.user.avatar.url)
        embed.add_field(name="Event Type", value=game_type, inline=False)
        embed.add_field(name="Event Date", value=game_date, inline=False)
        embed.add_field(name="Event Time", value=game_time, inline=False)
        embed.set_footer(text="This event was forced, bypassing the vote.")
        await Interaction.response.send_message(embed=embed)
        logger.warning(
            "========= Event succesfully added! Connection closed... ========="
        )
    except (psycopg2.Error, discord.DiscordException) as err:
        await Interaction.channel.send(
            f"======== An error has occured: ======== \n{str(err)}"
        )
        logger.error(
            "======== Error occured: ======== \n %s \nConnection closed...", str(err)
        )


@bot.tree.command(name="make-event", description="Creates a new event")
@app_commands.describe(
    game_type="Type of event - CPR or DND",
    game_date="Date of event - DD-MM-YYYY",
    game_time="Time of event - HH:MM",
)
async def make_eventvote(
    Interaction: discord.Interaction, game_type: str, game_date: str, game_time: str
):
    """Function to insert a new event into paps_table table provided it passes a vote"""
    await Interaction.response.defer()
    try:
        logger.info(
            "\n============== make-event command executed from discord! ================ Data received:\n %s \nType: %s, Date: %s, TIME: %s",
            Interaction.user,
            game_type,
            game_date,
            game_time,
        )

        # Some formatting of date and time to acceptable SQL format
        logger.info("Adjusting time format for %s to HH:MM...", game_time)
        game_time = game_time + ":00"  # Required, add seconds as 00 to query
        game_time = time.fromisoformat(
            game_time
        )  # Convert above to time object to insert to query.
        game_date = format_date(
            game_date, "%d-%m-%Y"
        )  # Formart EU standard date format to SQL date format.
        logger.info("Now initiating vote!")

        # Below, the voting process starts!
        # Set up some settings:
        thumbs_up = "👍"
        thumbs_down = "👎"
        voting_period = 86400  # in seconds, 86400 seconds = 1 day
        count_limit_success = 1
        count_limit_fail = 1
        # Create a neat embed to send with the relevant information:
        embed = discord.Embed(
            title="New event vote created!", color=discord.Color.green()
        )
        embed.set_author(name=Interaction.user, icon_url=Interaction.user.avatar.url)
        embed.add_field(name="Event Type", value=game_type, inline=False)
        embed.add_field(name="Event Date", value=game_date, inline=False)
        embed.add_field(name="Event Time", value=game_time, inline=False)
        embed.set_footer(text="Vote using 👍 If you can attend, and 👎 if you cannot.")
        # Send event details to discord channel.
        logger.info("Vote ready! - Sending vote to Discord.")
        event_message = await Interaction.followup.send(embed=embed)

        # Add thumbs-up and thumbs-down reactions to the message.
        await event_message.add_reaction(thumbs_up)
        await event_message.add_reaction(thumbs_down)

        # Set up event handlers to listen for reactions to the message, making sure to ignore the bots "vote".
        def check(reaction, user):
            return (
                user != bot.user
                and reaction.message.id == event_message.id
                and str(reaction.emoji) in [thumbs_up, thumbs_down]
            )

        try:
            logger.info("Now listening for votes.... fetching coffee while I wait.")
            # Vote counters here
            thumbs_up_count = 0
            thumbs_down_count = 0

            # Below we listen for pass conditions, and react accordingly.
            while True:
                reaction, _ = await bot.wait_for(
                    "reaction_add", timeout=voting_period, check=check
                )
                # Itteration counters for the emojis
                if reaction.emoji == thumbs_up:
                    thumbs_up_count += 1
                elif reaction.emoji == thumbs_down:
                    thumbs_down_count += 1

                # Pass condition reaction(Enough up-votes)
                if thumbs_up_count >= count_limit_success:
                    logger.info("Vote passed! Processing event to database...")
                    conn = create_connection()
                    cur = conn.cursor()

                    cur.execute(
                        "INSERT INTO paps_table (game_type, game_date, game_time) VALUES (%s, %s, %s)",
                        (game_type, game_date, game_time),
                    )
                    conn.commit()

                    cur.close()
                    conn.close()
                    logger.warning(
                        "========== Event added succesfully, sending to discord! ========"
                    )
                    await Interaction.channel.send(
                        "The event has received enough votes, and was saved!"
                    )
                    break

                # Fail condition reaction(Too many down-votes)
                if thumbs_down_count >= count_limit_fail:
                    logger.warning(
                        "========== Vote failed, too many down-votes... =========="
                    )
                    await Interaction.channel.send(
                        "The event received too many down-votes, and will not be saved!"
                    )
                    break

        # Fail condition(Vote timeout)
        except asyncio.TimeoutError:
            logger.warning("======= The voting period has ended(Timeout) ========")
            await Interaction.channel.send("Voting period has ended")
    except psycopg2.Error as err:
        logger.error("======= An error has occured: =======\n %s", str(err))
        await Interaction.channel.send(f"An error has occured: {str(err)}")


@bot.tree.command(name="list-events", description="List planned event(s)")
@app_commands.describe(
    game_id="ID of event - Unique ID",
    game_type="Type of event - CPR or DND",
    game_date="Date of event - DD-MM-YYYY",
    game_time="Time of event - HH:MM",
)
async def list_events(
    Interaction: discord.Interaction,
    *,
    game_id: str = None,
    game_type: str = None,
    game_date: str = None,
    game_time: str = None,
):
    """Function to fetch events, and send them to discord."""
    try:
        logger.info(
            "\n============== list-events command received from discord! ============\n %s \n Filtering by: %s",
            Interaction.user,
            game_id,
            game_type,
            game_date,
            game_time,
        )
        logger.info("Establishing connection to database...")
        conn = create_connection()
        logger.info("Connection established, creating SQL cursor...")
        cur = conn.cursor()

        # Base query to itterate upon
        query = (
            "SELECT game_id, game_type, game_date, game_time FROM paps_table WHERE TRUE"
        )
        logger.info("Established base query:\n %s", query)

        # Below we check if any filters were provided with the command, and act accordingly.
        logger.info("Fetching data...")
        try:
            if game_id is not None:
                query += " AND game_id = '%s'" % (game_id)
                logger.info("Sending query:\n %s", query)
                cur.execute(query)
            elif game_type is not None:
                game_type = game_type.lower()
                query += " AND game_type = '%s'" % (game_type)
                logger.info("Sending query:\n %s", query)
                cur.execute(query)
            elif game_date is not None:
                game_date = format_date(game_date, "%d-%m-%Y")
                if game_date:
                    query += " AND game_date = '%s'" % (game_date)
                    logger.info("Sending query:\n %s", query)
                    cur.execute(query)
            elif game_time is not None:
                query += " AND game_time = '%s'" % (str(game_time))
                logger.info("Sending query:\n %s", query)
                cur.execute(query)
            else:
                logger.warning("No valid filter applied...")
                query = (
                    "SELECT game_id, game_type, game_date, game_time FROM paps_table"
                )
                logger.info("Sending query:\n%s", query)
                cur.execute(query)

            rows = cur.fetchall()
        except (psycopg2.Error, discord.DiscordException) as err:
            await Interaction.channel.send(
                f"An error occurred while executing the query: {str(err)}"
            )
            return
        logger.info("Query sent! Fetch succesfull!")
        logger.info("Closing connection to database...")
        cur.close()
        conn.close()

        logger.info("Now processing fetch data...")
        logger.info("Creating discord embed object...")
        if rows:
            embed = discord.Embed(title="Events Results:", color=discord.Color.blue())
            embed.add_field(
                name="ID - Type - Date - Location", value="\u200b", inline=False
            )  # Header field
            for game_id, game_type, game_date, game_time in rows:
                row_info = f"{game_id} - {game_type} - {game_date} - {game_time}"  # Assemble SQL data
                embed.add_field(
                    name="\u200b", value=row_info, inline=False
                )  # Send SQL data
            logger.info("Discord embed created, data assembled, sending to discord...")
            await Interaction.response.send_message(embed=embed)
            logger.info("======== Discord message sent via Embed! ==========")
            """ OLD(await confirmation of to use embed)
        if rows:
            event_list = "\n".join(
                f"{game_id} - {game_type} - {game_date} - {game_time}"
                for game_id, game_type, game_date, game_time in rows
            )
            logger.info(
                "Processing succesfull! Final fetch:\n %s \n Sending to discord...",
                event_list,
            )
            await Interaction.response.send_message("Results:", ephemeral=True)
            await Interaction.channel.send(f"Current Events:\nID - TYPE - DATE - TIME\n{event_list}")
            logger.info("====== Discord message sent! =========")
            """
        else:
            logger.warning("========No events found from query...========")
            embed = embed = discord.Embed(
                title="Events Results:", color=discord.Color.red()
            )
            embed.add_field(name="No events found", value="There were no events found.")
            await Interaction.channel.send(embed=embed)
    except psycopg2.Error as err:
        logger.error("======== An error has occured: =======\n %s", str(err))
        await Interaction.channel.send(f"An error occurred: {str(err)}")


@bot.tree.command(name="delete-event", description="Delete an event by event ID")
@app_commands.describe(game_id="ID of event to delete")
async def delete_event(Interaction: discord.Interaction, game_id: int):
    """A function to delete events from database by game_id"""
    try:
        logger.info(
            "\n============ delete-event command received from discord! ===========\n %s \n ID to delete: %s",
            Interaction.user,
            game_id,
        )
        logger.info("Establishing connection...")
        conn = create_connection()
        logger.info("Connection succesfull, creating SQL cursor...")
        cur = conn.cursor()

        query = "DELETE FROM paps_table WHERE game_id = %s" % (game_id)
        logger.info("Query created: \n %s", query)
        cur.execute(query, (game_id,))
        conn.commit()
        logger.info("Sending query...")
        if cur.rowcount > 0:
            logger.info("Event succesfully deleted!")
            embed = discord.Embed(title="Delete Event", color=discord.Color.red())
            embed.set_author(
                name=Interaction.user, icon_url=Interaction.user.avatar.url
            )
            embed.add_field(
                name="Following event id has been deleted", value=game_id, inline=False
            )
            await Interaction.response.send_message(embed=embed)
        else:
            logger.warning("No event found by ID: %s", game_id)
            embed = discord.Embed(title="Delete Event", color=discord.Color.red())
            embed.set_author(
                name=Interaction.user, icon_url=Interaction.user.avatar.url
            )
            embed.add_field(
                name="No event was found by that id", value=game_id, inline=False
            )
            await Interaction.channel.send(embed=embed)

        cur.close()
        conn.close()
    except psycopg2.Error as err:
        logger.error(f"========= An error has occured: =========\n{str(err)}")
        await Interaction.channel.send(f"An error has occured: {str(err)}")


@bot.tree.command(name="edit-event", description="Edit event by event ID")
@app_commands.describe(
    game_id="Required, unique ID of event to edit",
    game_type="Game type to change event to",
    game_date="Date to change the event to",
    game_time="Time to change the event to",
)
async def edit_event(
    Interaction: discord.Interaction,
    game_id: int,
    game_type: str = None,
    game_date: str = None,
    game_time: str = None,
):
    """A function to edit existing events by id"""
    try:
        logger.info(
            "\n============ edit-event command received from discord! ===========\n %s \n Game ID to edit: %s \n %s, %s, %s",
            Interaction.user,
            game_id,
            game_type,
            game_date,
            game_time,
        )
        logger.info("Establishing connection to SQL database...")
        conn = create_connection()
        logger.info("Connection established, creating cursor...")
        cur = conn.cursor()

        query = "UPDATE paps_table SET"
        logger.info("Base query created: %s", query)
        if game_type:
            query += " game_type = '%s'," % (game_type)
            logger.info("Changing game type to: %s", game_type)
        elif game_date:
            query += " game_date = '%s'," % (game_date)
            logger.info("Changing game date to: %s", game_date)
        elif game_time:
            query += " game_time = '%s'," % (game_time)
            logger.info("Changing game time to: %s", game_time)
        else:
            Interaction.channel.send("No changes made...")

        # Remove the trailing comma from the query
        query = query.rstrip(",")

        query += " WHERE game_id = %s" % (game_id)
        cur.execute(query)
        logger.info("Final query:\n %s", query)
        logger.info("Sending query...")
        conn.commit()

        if cur.rowcount > 0:
            logger.info("======== Event ID: %s has been updated... ========", game_id)
            embed = discord.Embed(title="Edit Event", color=discord.Color.yellow())
            embed.set_author(
                name=Interaction.user, icon_url=Interaction.user.avatar.url
            )
            edit_field = f"{game_id} - {game_type} - {game_date} - {game_time}"
            embed.add_field(
                name="The following event has been edited",
                value=edit_field,
                inline=False,
            )
            await Interaction.response.send_message(embed=embed)
        else:
            logger.warning("========= No event found by ID:%s =========", game_id)
            embed = discord.Embed(title="Edit event", color=discord.Color.red())
            embed.set_author(
                name=Interaction.user, icon_url=Interaction.user.avatar.url
            )
            edit_field = f"{game_id} - {game_type} - {game_date} - {game_time}"
            embed.add_field(
                name="No event was found by game ID", value=game_id, inline=False
            )
            await Interaction.channel.send(embed=embed)

        logger.info("======= Closing connection... ========")
        cur.close()
        conn.close()
    except psycopg2.Error as err:
        logger.error("======== An error has occured: ========\n %s", str(err))
        await Interaction.channel.send(f"An error has occured: {str(err)}")


def start(token: str) -> None:
    """Function to wake the bot"""
    logger.info("Starting paps-bot ...")
    bot.run(token)

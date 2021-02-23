import datetime
import logging
import os
import random
import threading
import time
import warnings
from copy import copy
from signal import signal, SIGTERM, SIGINT

import compress_pickle
import dropbox
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ChatAction, InlineKeyboardMarkup, InlineKeyboardButton, \
    InputMediaPhoto
from telegram.error import Unauthorized, BadRequest
from telegram.ext import MessageHandler, Filters, Updater, CommandHandler, CallbackQueryHandler
from telegram.utils.helpers import escape_markdown, mention_markdown

import charts
import constants
import line_detection
from data import CPGameData
from scores import get_score, get_daily


def load_database(base: CPGameData):
    if not test_environment:
        db = dropbox.Dropbox(constants.DROPBOX_TOKEN)
        db.files_download_to_file(constants.DATABASE_PATH, constants.DROPBOX_PATH)
    if not test_environment or test_environment and os.path.exists(constants.DATABASE_PATH):
        try:
            _database = compress_pickle.load(constants.DATABASE_PATH)
        except EOFError:
            logging.error("Database corrupted.")
        else:
            logging.info(f"Loaded database from {constants.DATABASE_PATH}.")
            for param, value in _database.items():
                base[param] = value
    else:
        logging.info(f"No backup found.")
    return base


def backup_database(*args):
    compress_pickle.dump(dict(database), constants.DATABASE_PATH)

    if not test_environment:
        with open(constants.DATABASE_PATH, "rb") as f:
            updater.bot.send_document(
                chat_id=constants.ADMIN_USER,
                document=f,
            )
        if args:
            db = dropbox.Dropbox(constants.DROPBOX_TOKEN)
            db.files_delete(constants.DROPBOX_PATH)
            logging.info("deleted old database")
            with open(constants.DATABASE_PATH, "rb") as f:
                db.files_upload(f.read(), constants.DROPBOX_PATH)

    logging.info(f"Backed up database at {constants.DATABASE_PATH}.")
    if args:
        updater.stop()


def mention_from_id(user_id):
    chat = updater.bot.get_chat(user_id)
    name = chat.first_name + (" " + chat.last_name if chat.last_name else "")
    return mention_markdown(user_id, name, version=2)


def large(large_number):
    large_number = int(float(large_number))
    if large_number >= 10_000:
        out = str(large_number)
        return out[:len(out) % 3] + ",".join(out[len(out) % 3:][i:i + 3] for i in range(len(out) // 3))
    return str(large_number)


def get_flag(country):
    for label in constants.SUPPORTED_COUNTRIES:
        if label[3:] == country:
            return label[:2]
    logging.error(f"The country {country} is not supported.")
    return "  "


def get_country(flag):
    for label in constants.SUPPORTED_COUNTRIES:
        if label[:2] == flag:
            return label[3:]
    logging.error(f"The flag {flag} is not invalid.")
    return "⁇ Unknown Country"


def send_menu_markup(text: str, update, chat_id=None):
    markup = []
    for i in range(0, len(titles := list(MENU_OPTIONS.keys())) * 2, 2):
        markup.append(titles[i:i + 2])
    if chat_id:
        updater.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=ReplyKeyboardMarkup(
                markup,
                one_time_keyboard=True,
            ))
    else:
        update.message.reply_text(
            text=text,
            reply_markup=ReplyKeyboardMarkup(
                markup,
                one_time_keyboard=True,
            ))


def send_start_markup(text=None, update=None, chat_id=None):
    markup = [["/start"]]
    if chat_id:
        updater.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=ReplyKeyboardMarkup(
                markup,
                one_time_keyboard=True,
            ))
    else:
        update.message.reply_text(
            text=text,
            reply_markup=ReplyKeyboardMarkup(
                markup,
                one_time_keyboard=True,
            ))


def start(update, context, start_message=True):
    if update.message.chat.type != "private":
        start_group(update, context)
        return

    if context.args:
        context.user_data['challenge_active'] = True
        context.user_data['action'], challenge_id, chat_id, config_id = context.args[0].split("_")
        context.user_data['challenge_id'] = int(challenge_id)
        context.user_data['chat_id'], context.user_data['config_id'] = int(chat_id), int(config_id)
    elif start_message:
        context.user_data.clear()

    if context.user_data:
        actions = {
            'bet': give_challenge_prediction,
            'country': change_challenge_country,
            'confirm': confirm_challenge_prediction,
        }
        actions[context.user_data['action']](update, context)
        return

    global database
    send_menu_markup("Welcome to the Corona Prediction Game!", update)

    user_id = update.message.from_user.id
    if user_id not in database['users']:
        database['users'][user_id] = {
            'chart_scale': 1.5,
            'drawing_area': None,  # type: tuple
            'drawing_update': None,  # type: datetime.date
            'high_scores_view': None,  # type: str
            'last_conversation_state': constants.MENU,  # type: int
            'last_scheduled_update': None,  # type: datetime.datetime
            'last_update': list(constants.UPDATES.keys())[-1],
            'limits_note': False,
            'nickname': "<hidden>",
            'nickname_confirmed': False,
            'predictions': dict(),
            'recent_prediction': dict(),
            'recent_country': "",
            'scheduled_updates_interval': None,
            'scores': dict(),
            'scores_daily': dict(),
            'update_notifications': True,
        }
    else:
        database['users'][user_id]['last_conversation_state'] = constants.MENU

    if update.message.from_user.id == constants.ADMIN_USER:
        backup_database()
    return constants.MENU


def menu(update, context):
    return MENU_OPTIONS[update.message.text](update, context)


def select_country(update, _):
    markup = [[constants.SUPPORTED_COUNTRIES[0]]]
    for i in range(0, len(constants.SUPPORTED_COUNTRIES[1:]) * 3, 3):
        markup.append(constants.SUPPORTED_COUNTRIES[i + 1:i + 4])

    update.message.reply_text("Please select a country.",
                              reply_markup=ReplyKeyboardMarkup(
                                  markup,
                                  one_time_keyboard=True
                              ))
    return constants.GIVE_PREDICTION


def prediction_caption(user_data):
    country = user_data['recent_country']
    res = charts.visualize_for_input(country, database, chart_scale=user_data['chart_scale'])
    if res:
        user_data['drawing_area'] = res
        user_data['drawing_update'] = datetime.date.today()

    if country in user_data['predictions'].keys():
        warning = f"\n\n⚠ You already gave a prediction for this country. If you continue, it will be deleted and the" \
                  f" score will be 0 again."
    else:
        warning = ""

    caption = f"📈Alright, here are the daily new cases of Covid-19 " \
              f"{'for the whole' if country == 'World' else 'in'} {country}. How will the pandemic continue?\n\n" \
              f"Download the image and draw your estimate with the Telegram app or a software of your choice. Then" \
              f" upload the edited image in this chat. Your drawn line will be detected automatically!\n\n " \
              f"Use /start to go back.{warning}"

    reply_markup = InlineKeyboardMarkup.from_row([
        InlineKeyboardButton("↕️ zoom out", callback_data="user|scale|inc"),
        InlineKeyboardButton("🔍 zoom in", callback_data="user|scale|dec"),
        InlineKeyboardButton("🔄 reset zoom", callback_data="user|scale|reset")
    ])
    return caption, reply_markup


def give_prediction(update, _):
    global database
    if update.message.text not in constants.SUPPORTED_COUNTRIES:
        markup = [[constants.SUPPORTED_COUNTRIES[0]]]
        for i in range(0, len(constants.SUPPORTED_COUNTRIES[1:]) * 3, 3):
            markup.append(constants.SUPPORTED_COUNTRIES[i + 1:i + 4])
        update.message.reply_text(
            text="Please select a country from the markup keyboard. If you cannot see the country list, tap on the symb"
                 "ol with four squares on the right side next to the message field.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=markup,
                one_time_keyboard=True
            )
        )
        return constants.GIVE_PREDICTION

    country = update.message.text[3:]
    user_id = update.message.from_user.id
    user_data = database['users'][user_id]

    # noinspection PyTypeChecker
    updater.bot.send_chat_action(user_id, ChatAction.UPLOAD_PHOTO)
    user_data['recent_country'] = country
    caption, reply_markup = prediction_caption(user_data)

    with open(f"{charts.IMAGES_PATH}/{country}.jpg", "rb") as f:
        update.message.reply_photo(
            photo=f,
            caption=caption,
            reply_markup=reply_markup,
        )
    return constants.CONFIRM_PREDICTION


def confirm_prediction(update, _):
    global database
    user_id = update.message.from_user.id
    # noinspection PyTypeChecker
    updater.bot.send_chat_action(user_id, ChatAction.UPLOAD_PHOTO)
    country = database['users'][user_id]['recent_country']
    drawing_area = database['users'][user_id]['drawing_area']

    file = update.message.photo[-1].get_file()

    temp_lock.acquire()
    try:
        file.download(custom_path=constants.TEMP_PATH)
        raw_predictions = line_detection.evaluate(constants.TEMP_PATH, country, drawing_area, database)
        if type(raw_predictions) == str:
            update.message.reply_text(raw_predictions)
            return constants.CONFIRM_PREDICTION
        database['users'][user_id]['recent_prediction'] = raw_predictions
        charts.visualize_for_confirmation(country, raw_predictions, constants.TEMP_PATH, database,
                                          database['users'][user_id]['chart_scale'])
        with open(constants.TEMP_PATH, "rb") as f:
            update.message.reply_photo(
                photo=f,
                caption="This is how your line is detected. Is everything okay here?",
                reply_markup=ReplyKeyboardMarkup(
                    [["✅ Seems right, continue"], ["⏪ No, go back"]],
                    one_time_keyboard=True
                )
            )
    finally:
        temp_lock.release()
    return constants.LINK_ACCOUNT


def link_account(update, _):
    global database
    user_id = update.message.from_user.id

    if "no" in update.message.text.lower():
        update.message.reply_text(
            text="🔄 If you want to, you can send the picture again. At any time, /start can be used to get back to the "
                 "menu.",
            reply_markup=ReplyKeyboardRemove()
        )
        return constants.CONFIRM_PREDICTION

    elif "right" in update.message.text.lower() or "yes" in update.message.text.lower():
        database['users'][user_id]['predictions'][
            database['users'][user_id]['recent_country']] = \
            database['users'][user_id]['recent_prediction']
        database['users'][user_id]['scores'][
            database['users'][user_id]['recent_country']] = 0
        database['high_scores'].append((0, user_id, database['users'][user_id]['recent_country']))
        database['high_scores_daily'].append((0, user_id, database['users'][user_id]['recent_country']))
        if database['users'][user_id]['nickname_confirmed']:
            send_menu_markup("✅ Cool, your estimate has been saved.", update)
            return constants.MENU

        update.message.reply_text(
            text="Cool, right now you officially participated in the Corona Prediction Game. Your Performance might be "
                 "visible to everyone in the High Score section. How do you want to appear there?",
            reply_markup=ReplyKeyboardMarkup(
                [[f"Link my username (@{update.message.from_user.username})"],
                 ["Use a custom nickname"], ["Keep my identity hidden"]],
                one_time_keyboard=True
            )
        )
        return constants.DO_LINK
    else:
        update.message.reply_text(
            text="🧐 Sorry, does this image represent your estimate? Use /start to abort and get to the main menu.",
            reply_markup=ReplyKeyboardMarkup(
                [["✅ Yes, Continue"], ["⏪ No, Go Back"]],
                one_time_keyboard=True
            )
        )
        return constants.LINK_ACCOUNT


def do_link(update, context):
    global database
    user_id = update.message.from_user.id

    if "username" in update.message.text.lower():
        database['users'][user_id]['nickname'] = f"@{update.message.from_user.username}"
        database['users'][user_id]['nickname_confirmed'] = True
        send_menu_markup("✅ Your choice was saved.", update)
        return constants.MENU
    elif "hidden" in update.message.text.lower():
        database['users'][user_id]['nickname'] = "<hidden>"
        database['users'][user_id]['nickname_confirmed'] = True
        send_menu_markup("✅ Your choice was saved.", update)
        return constants.MENU
    elif "nickname" in update.message.text.lower():
        update.message.reply_text(
            text="Please enter your custom nickname now.",
            reply_markup=ReplyKeyboardRemove()
        )
        return constants.CUSTOM_NICKNAME
    else:
        return custom_nickname(update, context)


def custom_nickname(update, _):
    if len(new_nickname := update.message.text) > 30:
        update.message.reply_text(
            text="This nickname is pretty long - Please keep it below 30 characters. And again: What shall be your "
                 "name in the High Scores section? You can use /start to go back to the menu at any time.",
            reply_markup=ReplyKeyboardRemove()
        )
        return constants.CUSTOM_NICKNAME

    global database
    user_id = update.message.from_user.id
    database['users'][user_id]['nickname'] = new_nickname
    database['users'][user_id]['nickname_confirmed'] = True

    send_menu_markup("✅ Your choice was saved.", update)
    return constants.MENU


def preferences(update, _):
    if update.message.chat.type != "private":
        update.message.reply_text(
            "There are no settings in the group mode. This command is available for privat chats "
            "only.")
        return
    user = database['users'][update.message.from_user.id]
    interval = user['scheduled_updates_interval']
    scheduled_updates_text = {
        datetime.timedelta(days=1): "sent daily",
        datetime.timedelta(days=7): "sent weekly",
    }[interval] if interval else "disabled"

    update.message.reply_text(f"Your nickname is currently set to {user['nickname']}.\n"
                              f"Scheduled notifications are {scheduled_updates_text}.\n"
                              f"Major update notifications are "
                              f"{('disabled', 'enabled')[user['update_notifications']]}.\n",
                              reply_markup=ReplyKeyboardMarkup(
                                  [["📝 Change Nickname"],
                                   ["notify daily", "notify weekly",
                                    "no scheduled notifications"],
                                   ["Toggle Notifications"],
                                   ["⏪ Go Back"]],
                                  one_time_keyboard=True
                              ))
    database['users'][update.message.from_user.id]['last_conversation_state'] = constants.CHANGE_PREFERENCES
    return constants.CHANGE_PREFERENCES


def change_preferences(update, context):
    response = update.message.text.lower()
    if "change" in response:
        update.message.reply_text(
            text="What shall be your name in the High Scores section?",
            reply_markup=ReplyKeyboardMarkup(
                [[f"Link my username (@{update.message.from_user.username})"],
                 ["Use a custom nickname"],
                 ["Keep my identity hidden"]],
                one_time_keyboard=True
            )
        )
        return constants.DO_LINK
    elif "daily" in response:
        user = database['users'][update.message.from_user.id]
        user['scheduled_updates_interval'] = datetime.timedelta(days=1)
        user['last_scheduled_update'] = datetime.date.today()
        preferences(update, context)
    elif "weekly" in response:
        user = database['users'][update.message.from_user.id]
        user['scheduled_updates_interval'] = datetime.timedelta(days=7)
        user['last_scheduled_update'] = datetime.date.today()
        preferences(update, context)
    elif "scheduled" in response:
        user = database['users'][update.message.from_user.id]
        user['scheduled_updates_interval'] = None
        preferences(update, context)
    elif "notification" in response:
        user = database['users'][update.message.from_user.id]
        user['update_notifications'] = 1 - user['update_notifications']
        preferences(update, context)
    elif "back" in response:
        return start(update, context)
    else:
        return fancy_error(update, context)


def high_scores(update, context):
    global database
    if "back" in update.message.text.lower():
        return start(update, context)

    content = update.message.text.lower()
    user_id = update.message.from_user.id

    daily = "daily" in content or "total" not in content and database['users'][user_id][
        'high_scores_view'] == "daily"
    if daily:
        database['users'][user_id]['high_scores_view'] = "daily"
    else:
        database['users'][user_id]['high_scores_view'] = "total"

    highscores = database[('high_scores', 'high_scores_daily')[daily]]

    formatted_highscores = []
    for i, (score, user_id_, country) in enumerate(highscores, start=1):
        if user_id_ == user_id:
            formatted_highscores.append(
                f"#{i} {get_flag(country)} {score:.3f}: {database['users'][user_id_]['nickname']} <-- you")
        elif i <= 10:
            formatted_highscores.append(
                f"#{i} {get_flag(country)} {score:.3f}: {database['users'][user_id_]['nickname']}")

    if daily:
        response = "Average Score per Day\n\n"
    else:
        response = "Total Score\n\n"
    response += "\n".join(formatted_highscores[:10] + [""] + formatted_highscores[10:])
    response += f"\n\ntotal predictions: {len(highscores)}"

    update.message.reply_text(
        text=response,
        reply_markup=ReplyKeyboardMarkup(
            [["⏪ Go Back"],
             ["Show Daily"],
             ["Show Total"]],
            one_time_keyboard=True,
        ))
    return constants.HIGH_SCORES


def about(update, _):
    send_menu_markup("This is version 2.0.0. \nChangelog: @cpgame_changelog\nGitHub: "
                     "https://github.com/jschoedl/corona-prediction-game\n\n"
                     "This bot is using a dataset maintained by 'Our World in Data'. You can find it "
                     "here: https://github.com/owid/covid-19-data/tree/master/public/data\n\n"
                     "The idea for this bot was inspired by @reispflanze, "
                     "who also designed its logo. The bot itself was written in Python by me, @Jakob_Schoedl. Do not "
                     "hesitate to contact me with your feedback, bugs and problems!", update)
    return constants.MENU


def user_predictions(update, _):
    global database
    user_id = update.message.from_user.id
    scores: dict = database['users'][user_id]['scores']

    if not scores:
        update.message.reply_text(
            text="You have not given any predictions.",
            reply_markup=ReplyKeyboardMarkup(
                [["➕ New Prediction", "⏪ Go Back"]],
                one_time_keyboard=True
            ),
        )
        return constants.COUNTRY_DETAILS
    else:
        text = "Every day, you can get up to 1 point per country, depending on how close your estimate is to the " \
               "number of actually reported cases. If you give a new prediction for a country, its score counter will" \
               " start at 0 again.\n\n"

        for country, score in scores.items():
            text += f"{get_flag(country)} {country}: {score:.3f}\n"
        text += f"\nYou gave predictions for {len(scores)} countr{'ies' if len(scores) > 1 else 'y'}. Tap on a " \
                f"country to get more details about it!"
        update.message.reply_text(
            text=text,
            reply_markup=ReplyKeyboardMarkup(
                [["➕ New Prediction", "⏪ Go Back"]] + [[f"{get_flag(i)} {i}"] for i in
                                                       scores.keys()]
            )
        )
        return constants.COUNTRY_DETAILS


def country_details(update, context):
    user_data = database['users'][update.message.from_user.id]
    if "new" in update.message.text.lower():
        return select_country(update, context)
    elif "back" in update.message.text.lower():
        return start(update, context)
    elif (country := update.message.text[3:]) in user_data['predictions']:
        # noinspection PyTypeChecker
        updater.bot.send_chat_action(update.message.from_user.id, ChatAction.UPLOAD_PHOTO)
        country_predictions = user_data['predictions'][country]
        temp_lock.acquire()
        try:
            charts.visualize([country, country], [country_predictions, country_predictions], constants.TEMP_PATH,
                             database,
                             titles=[f"Daily reported Covid-19-infections "
                                     f"{'for the whole' if country == 'World' else 'in'} {country}", ""],
                             offsets=[[300, 300], [10, 10]])
            with open(constants.TEMP_PATH, "rb") as f:
                update.message.reply_photo(
                    photo=f
                )
        finally:
            temp_lock.release()
        return constants.COUNTRY_DETAILS
    else:
        fancy_error(update, context)


def help_(update, context):
    if update.message.chat.type == "private":
        send_menu_markup(
            text="This is the Corona Prediction Game. Send /start to get to the main menu.\n\n"
                 "If you want to give a new prediction, tap \"new prediction\" and select your country.\n\n"
                 "If you have a question or spotted a bug, let me know here: @Jakob_Schoedl",
            update=update
        )
        database['users'][update.message.from_user.id]['last_conversation_state'] = constants.MENU
    else:
        update.message.reply_text(
            text="You can start a new group challenge using one of the following commands:\n\n"
                 "/7dayschallenge\n/30dayschallenge\n/100dayschallenge\n/oneyearchallenge\n\n"
                 "If you have a question or spotted a bug, let me know here: @Jakob_Schoedl\n"
                 "Message this bot directly to give more advanced predictions."
        )


def challenge_text(configuration):
    return f"*New Challenge*\n\n" \
           f"country: {get_flag(configuration['country'])}{configuration['country']}\n" \
           f"duration: {configuration['duration'].days} days\n" \
           f"submissions will be {configuration['submissions']} before challenge ends"


def challenge_markup(chat_id, config_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("abort", callback_data="config_c|abort"),
         InlineKeyboardButton("change country",
                              url=f"t.me/{updater.bot.username}?start=country_0_{chat_id}_{config_id}")],
        [InlineKeyboardButton("toggle visibility", callback_data="config_c|publicity"),
         InlineKeyboardButton("start challenge", callback_data="config_c|start")],
    ])


def start_group(update, context, added=False):
    if update.effective_chat.id not in database['groups']:
        update.message.reply_text(
            "This is the Corona Prediction Game on Telegram. You can start a group challenge using "
            "one of the following commands:\n\n"
            "/7dayschallenge\n/30dayschallenge\n/100dayschallenge\n/oneyearchallenge\n\n"
            "All members of this group can participate in the challenge. Just try it out - you'll "
            "get more details later.\n\n"
            "Group challenges are in beta. Please report bugs to @Jakob_Schoedl.")
        database['groups'][update.effective_chat.id] = {
            'configurations': dict(),
        }
    elif added:
        return


def group_challenge(update, context, duration: datetime.timedelta):
    if update.message.chat.type == "private":
        update.message.reply_text("You can't do a challenge without others. Add me to a group! :)")
        return

    configuration = {
        'user': update.message.from_user.id,
        'country': "World",
        'duration': duration,
        'submissions': "hidden",
        'bets': dict(),
    }

    charts.visualize_for_input(country=configuration['country'],
                               covid_stats=database,
                               end_date=datetime.date.today() + datetime.timedelta(days=7),
                               chart_scale=1.1,
                               starting_date=datetime.date.today() - max(
                                   configuration['duration'],
                                   datetime.timedelta(days=30)),
                               )

    config_id = update.message.reply_photo(
        caption="⏳",
        photo=open(f"{charts.IMAGES_PATH}/{configuration['country']}.jpg", "rb"),
    ).message_id

    updater.bot.edit_message_caption(
        chat_id=update.effective_chat.id,
        message_id=config_id,
        caption=challenge_text(configuration),
        parse_mode="MarkdownV2",
        reply_markup=challenge_markup(update.effective_chat.id, config_id)
    )
    database['groups'][update.effective_chat.id]['configurations'][config_id] = configuration


def change_challenge_country(update, context):
    configuration = database['groups'][context.user_data['chat_id']]['configurations'][context.user_data['config_id']]
    if update.message.text in constants.SUPPORTED_COUNTRIES:
        configuration['country'] = update.message.text[3:]
        update.message.reply_text("✅ The country was changed. You can go back now or change it again.")

        update_challenge_chart(configuration, context)

        updater.bot.edit_message_caption(
            chat_id=context.user_data['chat_id'],
            message_id=context.user_data['config_id'],
            caption=challenge_text(configuration),
            reply_markup=challenge_markup(context.user_data['chat_id'], context.user_data['config_id']),
            parse_mode="MarkdownV2"
        )
    else:
        markup = [[constants.SUPPORTED_COUNTRIES[0]]]
        for i in range(0, len(constants.SUPPORTED_COUNTRIES[1:]) * 3, 3):
            markup.append(constants.SUPPORTED_COUNTRIES[i + 1:i + 4])

        update.message.reply_text(
            "Please select a country from the markup keyboard. If you cannot see the country list, "
            "tap on the symbol with four squares on the right side next to the message field.",
            reply_markup=ReplyKeyboardMarkup(
                markup,
                one_time_keyboard=True
            ))


def update_challenge_chart(configuration, context=None):
    if context:
        chat_id = context.user_data['chat_id']
        message_id = context.user_data['config_id']
        end = datetime.date.today() + configuration['duration']
    else:
        chat_id = configuration['chat_id']
        message_id = configuration['message_id']
        end = configuration['end']

    charts.visualize_for_input(country=configuration['country'],
                               covid_stats=database,
                               end_date=end,
                               chart_scale=1.1,
                               starting_date=datetime.date.today() - configuration['duration'] * 3,
                               )
    updater.bot.edit_message_media(
        chat_id=chat_id,
        message_id=message_id,
        media=InputMediaPhoto(open(f"{charts.IMAGES_PATH}/{configuration['country']}.jpg", "rb")),
    )


def update_challenge_text(configuration):
    if datetime.datetime.now() < configuration['submission_end']:
        text = escape_markdown(
            f"Everyone in the group can now participate in the challenge.\n\n"
            f"How many Covid-19-Infections will be reported in"
            f"{' the whole' if configuration['country'] == 'World' else ''} {configuration['country']} on "
            f"{configuration['end'].strftime('%A, %B %d')}? Hit the button below and tap 'start'.\n\n"
            f"time left for submissions: "
            f"< {(configuration['submission_end'] - datetime.datetime.now()).total_seconds() // 3600 + 1:.0f} hours\n"
            f"challenge duration: {configuration['duration'].days} days\n\n",
            version=2
        )

        if not configuration['bets']:
            text += "\(no participants up to now\)"
        else:
            text += f"{len(configuration['bets'])} participant{'s' if len(configuration['bets']) > 1 else ''}:\n"

        if len(configuration['bets']) < 50:
            for user_id in configuration['bets']:
                text += mention_from_id(user_id) + "\n"

        try:
            updater.bot.edit_message_caption(
                chat_id=configuration['chat_id'],
                message_id=configuration['message_id'],
                caption=text,
                reply_markup=InlineKeyboardMarkup.from_button(
                    InlineKeyboardButton("➡️ add your estimate",
                                         url=f"t.me/{updater.bot.username}?start=bet_{configuration['id']}_0_0")
                ),
                parse_mode="MarkdownV2"
            )
        except BadRequest:
            pass
        return

    if len(configuration['bets']) < 2:
        updater.bot.edit_message_caption(
            chat_id=configuration['chat_id'],
            message_id=configuration['message_id'],
            caption="❌ Because less than two people participated, the challenge was aborted."
        )
        del database['challenges'][configuration['id']]
        return

    last_date, new_cases = database.get('date', 'new_cases_smoothed', location=configuration['country'])[-1]

    text = f"How many Covid-19-Infections will be reported in" \
           f"{' the whole' if configuration['country'] == 'World' else ''} {configuration['country']} on " \
           f"{configuration['end'].strftime('%A, %B %d')}? {len(configuration['bets'])} people participated in the " \
           f"challenge"

    if configuration['submissions'] == "hidden":
        text += ". All submissions remain private until the challenge ends.\n"
    elif len(configuration['bets']) > 50:
        text += "Too many people participated in this challenge, therefore unique predictions cannot be shown.\n\n" \
                "highest prediction:\n"
        user_id, prediction = max(configuration['bets'].items(), key=lambda i: i[0])
        text += f"{mention_from_id(user_id)}: {large(prediction)}\n\nlowest prediction:\n"
        user_id, prediction = min(configuration['bets'].items(), key=lambda i: i[0])
        text += f"{mention_from_id(user_id)}: {large(prediction)}\n\naverage prediction:\n" \
                f"{large(sum(prediction.values()) / len(prediction))}\n"
    elif configuration['submissions'] == "public":
        text += ":\n\n"
        for user_id, prediction in sorted(configuration['bets'].items()):
            text += f"{mention_from_id(user_id)}: {large(prediction)}\n"
    else:
        logging.critical(f"Submissions in configuration {configuration['id']} are neither hidden nor public.")
        text += ".\n"

    text += f"\nNew cases on {datetime.date.fromisoformat(last_date).strftime('%A, %B %d')} (7-day-smoothed):\n{large(new_cases)}"
    updater.bot.edit_message_caption(
        chat_id=configuration['chat_id'],
        message_id=configuration['message_id'],
        caption=text
    )

    if datetime.date.fromisoformat(last_date) > configuration['end']:
        new_cases = database.get('new_cases_smoothed', date=configuration['end'].isoformat(),
                                 country=configuration['country'])
        new_cases = float(new_cases[0][0])
        score_list = sorted(configuration['bets'].items(), key=lambda i: abs(i[1] - new_cases))
        text = f"The challenge from {(configuration['end'] - configuration['duration']).strftime('%A, %B %d')} with " \
               f"{len(configuration['bets'])} participants ended now\. Congratulations, " \
               f"{mention_from_id(score_list[0][0])}\!\n\nReported Cases: {large(new_cases)}\n\n" \
               f"🏅{mention_from_id(score_list[0][0])}: {large(score_list[0][1])}\n"

        for i, (user_id, prediction) in enumerate(score_list[1:50], start=2):
            text += f"\#{i} {mention_from_id(user_id)}: {large(prediction)}\n"

        updater.bot.send_message(
            configuration['chat_id'],
            text=text,
            parse_mode="MarkdownV2",
            reply_to_message_id=configuration['message_id'],
        )
        del database['challenges'][configuration['id']]


def give_challenge_prediction(update, context):
    configuration = database['challenges'][context.user_data['challenge_id']]
    update.message.reply_text(
        f"How many Covid-19-Infections will be reported in"
        f"{' the whole' if configuration['country'] == 'World' else ''} "
        f"{configuration['country']} on {configuration['end'].strftime('%A, %B %d')}? Send me your bet for this "
        f"specific day only.\n\nexamples for valid formats:\n42\n45.3k\n141000"
    )
    context.user_data['action'] = "confirm"


def confirm_challenge_prediction(update, context):
    configuration = database['challenges'][context.user_data['challenge_id']]
    if datetime.datetime.now() > configuration['submission_end']:
        update.message.reply_text("You are too late for this challenge. Sorry!\n\nIf you want to participate in the"
                                  "global Corona Prediction Game without a group, send /start again.")
    message: str = update.message.text.lower()
    for char in "√∛∜∞÷×∑π¼½²³¾":
        if char in message:
            update.message.reply_text("🧐")
            answers = ("Hey,", "Come on,", "I'm sorry, but", "Ehm, I am a bit confused -")
            update.message.reply_text(
                f"{random.choice(answers)} don't leave everything up to me just because I can do maths faster "
                "than you! Just a rational number in non-mathematician-notation, please. :)")
            return

    if message != "0":
        message = message.replace("k", "000").replace("m", "000000")
        if message.count(".") > 1:
            message = message.replace(".", "")
        if message.count(",") > 1:
            message = message.replace(",", ".")
        message = message.replace(",", ".")
        message = "".join(char for char in message if ord("0") <= ord(char) <= ord("9") or char == ".")

    if message and ((bet := float(message)) or message == "0"):
        bet = float(message)

        configuration['bets'][update.message.from_user.id] = bet

        update_challenge_text(configuration)

        response = f"✅Your prediction was saved:\n{large(bet)} new reported infections on " \
                   f"{configuration['end'].strftime('%B %d')}. You can go back now. If you want to change something, " \
                   f"just send another value."

        if bet > 7_800_000_042:
            first = random.choice(("Frankly speaking", "Honestly", "Actually", "To be honest", "Hmm"))
            second = random.choice(("this", "your prediction", "your bet", "this number"))
            third = random.choice(("is", "seems", "feels"))
            fourth = random.choice(
                ("a bit", "really", "somewhat", "to some extent", "more the less", "kind of", "rather"))
            fifth = random.choice(("unrealistic", "unlikely to happen", "hard to imagine"))
            response += f"\n\n{first}, {second} {third} {fourth} {fifth}, because there are not enough people living on " \
                        "earth yet. But who knows about the future - I'll leave that up to you."

        elif update.message.from_user.id not in database['users']:
            response += "\n\nYou want to give more advanced predictions and get into the worldwide High Scores? Just " \
                        "send /start again!"
    else:
        response = "I did not quite get that. Please try it again - just send a number!"

    update.message.reply_text(response)


def set_challenge_updater(challenge_id, first=True):
    try:
        update_challenge_chart(database['challenges'][challenge_id])
    except BadRequest:
        pass
    update_challenge_text(database['challenges'][challenge_id])
    logging.info(f"updated challenge {challenge_id}")

    submission_end = database['challenges'][challenge_id]['submission_end']
    if datetime.datetime.now() < submission_end and first:
        time_to_submission_end = (submission_end - datetime.datetime.now()).total_seconds()
        threading.Timer(min(3600, time_to_submission_end), set_challenge_updater, [challenge_id]).start()


def configure_challenge(query):
    action = query.data.split("|")[1]
    configuration = database['groups'][query.message.chat_id]['configurations'][query.message.message_id]

    if query.from_user.id != configuration['user']:
        return "You have got no permission to edit this challenge."
    if action == "abort":
        del configuration
        query.edit_message_caption("❌ The Challenge was aborted.")
    elif action == "publicity":
        if configuration['submissions'] == "hidden":
            configuration['submissions'] = "public"
        else:
            configuration['submissions'] = "hidden"
        query.edit_message_caption(
            caption=challenge_text(configuration),
            reply_markup=challenge_markup(query.message.chat_id, query.message.message_id),
            parse_mode="MarkdownV2"
        )
    elif action == "start":
        configuration['end'] = datetime.date.today() + configuration['duration']
        configuration['submission_end'] = datetime.datetime.now() + datetime.timedelta(days=1)
        challenge_id = hash(time.time())
        configuration['id'] = challenge_id
        configuration['chat_id'] = query.message.chat_id
        configuration['message_id'] = query.message.message_id

        database['challenges'][challenge_id] = copy(configuration)

        update_challenge_text(configuration)
        del configuration

        set_challenge_updater(challenge_id)


def configure_user(query):
    action, param = query.data.split("|")[1:]
    user_data = database['users'][query.from_user.id]

    if action == "scale":
        if param == "inc":
            user_data['chart_scale'] *= 1.5
        elif param == "dec":
            user_data['chart_scale'] /= 1.5
        elif param == "reset":
            user_data['chart_scale'] = 1.5
        query.answer("✅The chart scale has been changed.")

        caption, reply_markup = prediction_caption(user_data)

        query.edit_message_media(
            media=InputMediaPhoto(open(f"{charts.IMAGES_PATH}/{user_data['recent_country']}.jpg", mode="rb")),
        )
        query.edit_message_caption(
            caption=caption,
            reply_markup=reply_markup,
        )


def fancy_error(update, _, type_error=False, internal_error=False):
    first = (
        "Wow", "Hey", "Oops", "Wait", "Sorry", "Wait a minute", "Oh no", "Well", "Ouch")
    second = ("this", "this message", "your response", "this response")
    third = (
        "was unexpected", "does not fit in this context", "is invalid",
        "does not match here",
        "could not be interpreted")
    if random.random() < 0.01:
        update.message.reply_text(
            text=constants.SECRET_ERROR
        )
        return

    if internal_error:
        text = f"{random.choice(first)}, something went wrong. This is an internal error and (probably) not your fault."
    else:
        if type_error:
            to_append = "\nPlease select an option from the markup keyboard! Just tap on the icon on the right side " \
                        "next to the text box. Tap /start to get back to the menu."
        else:
            to_append = ""
        text = f"{random.choice(first)}, {random.choice(second)}{' type' if type_error else ''} " \
               f"{random.choice(third)}.{to_append}"

    if internal_error:
        markup = ReplyKeyboardMarkup([["/start"]])
    else:
        markup = None
    update.message.reply_text(
        text=text,
        reply_markup=markup,
    )


def invalid_type(update, context):
    fancy_error(update, context, type_error=True)


def upgrade_user_data(users, user_params):
    """
    For compatibility with databases from previous versions
    """
    for user_id, user_data in users.items():
        for param, standard in user_params.items():
            if param not in user_data:
                user_data[param] = copy(standard)
                logging.info(
                    f"Parameter {param} not found for user {user_id}, added default value.")
        users[user_id] = user_data


def update_database():
    """
    Download new Covid-19-statistics and send special types of notifications every 24h.
    """
    # download new statistics and update scores
    logging.info(f"last scores update: {database['scores_update']}")
    if database['scores_update'] != datetime.datetime.now().date():
        logging.info("updating..")
        database.update_stats()

        highscores, highscores_daily = [], []
        for user_id, user_data in database['users'].items():
            for country, prediction in user_data['predictions'].items():
                score, scores_daily = get_score(country, database, get_daily(prediction))
                highscores.append((score, user_id, country))
                highscores_daily.append((scores_daily, user_id, country))
                user_data['scores'][country], user_data['scores_daily'][country] = score, scores_daily

        highscores.sort(reverse=True, key=lambda x: x[0])
        highscores_daily.sort(reverse=True, key=lambda x: x[0])

        database['high_scores'] = highscores
        database['high_scores_daily'] = highscores_daily
        database['scores_update'] = datetime.datetime.now().date()

        # send pending messages
        users = database['users']
        for user_id, user_data in copy(users).items():
            # update notifications
            if user_data['update_notifications']:
                for update_id, text in constants.UPDATES.items():
                    if user_data['last_update'] < update_id:
                        try:
                            send_start_markup(text, chat_id=user_id)
                            user_data['last_update'] = update_id
                        except Unauthorized:
                            try:
                                del users[user_id]
                                logging.info(f"Removed user {user_id}")
                            except:
                                logging.error(f"Could not remove {user_id}")
            # scheduled updates
            if user_id in users and user_data['scheduled_updates_interval']:
                if not user_data['last_scheduled_update']:
                    logging.error(
                        f"No last scheduled update interval set for user {user_id}.")
                elif not user_data['predictions']:
                    logging.error(
                        f"No predictions by user {user_id} available.")
                else:
                    try:
                        if datetime.date.today() - user_data['last_scheduled_update'] >= \
                                user_data['scheduled_updates_interval']:
                            try:
                                # noinspection PyTypeChecker
                                updater.bot.send_chat_action(user_id, ChatAction.UPLOAD_PHOTO)

                                greetings = ("Hi", "Hey", "Hello", "What's up", "Cheers")
                                chat = updater.bot.get_chat(user_id)
                                name = chat.first_name + (" " + chat.last_name if chat.last_name else "")
                                if not user_data['limits_note']:
                                    note = " Due to limitations of Telegram, I have to send it as a document."
                                    user_data['limits_note'] = True
                                else:
                                    note = ""
                                temp_lock.acquire()
                                try:
                                    charts.visualize(user_data['predictions'].keys(),
                                                     user_data['predictions'].values(),
                                                     constants.TEMP_PATH, database)
                                    # send uncompressed
                                    with open(constants.TEMP_PATH, "rb") as f:
                                        updater.bot.send_document(
                                            chat_id=user_id,
                                            document=f,
                                            caption=f"{random.choice(greetings)} {name}, here is your prediction report!{note}"
                                        )
                                finally:
                                    temp_lock.release()
                                user_data['last_scheduled_update'] = datetime.date.today()
                            except Unauthorized:
                                try:
                                    del users[user_id]
                                    logging.info(f"Removed user {user_id}")
                                except:
                                    logging.error(f"Could not remove {user_id}")
                    except Exception as e:
                        logging.error(f"user {user_id}: {e}")

        # update challenges
        for challenge_id in database['challenges']:
            set_challenge_updater(challenge_id, first=False)

    now = datetime.datetime.now()
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day)

    logging.info(f"next database update: {(tomorrow - now)}")

    threading.Timer((tomorrow - now).total_seconds(), update_database).start()


def handle_message(update, context):
    if (chat_type := update.message.chat.type) != "private":
        if chat_type in ("group", "supergroup"):
            if not len(update.message.entities):
                start_group(update, context, added=True)
        return

    if context.user_data:
        start(update, context, start_message=False)
        return

    user = update.message.from_user
    if user.id in database['users'] and (state := database['users'][user.id]['last_conversation_state']):
        try:
            for handler in conversation_states[state]:
                if handler.check_update(update):
                    conversation_state = handler.callback(update, context)
                    logging.info("(%s) %s: %s -> %s", state, user.username, update.message.text,
                                 conversation_state)
                    if isinstance(conversation_state, int):
                        database['users'][user.id]['last_conversation_state'] = conversation_state
                    break
            else:
                logging.info("(%s) %s: %s -> !!! unexpected type", state, user.username, update.message.text)
                fancy_error(update, context, type_error=True)
        except Exception:
            logging.exception("(%s) %s: %s -> !!!", state, user.username, update.message.text)
            fancy_error(update, context, internal_error=True)
    else:
        logging.error("(no conversation state) %s: %s -> ???", user.username, update.message.text)
        fancy_error(update, context, internal_error=True)


def handle_callback(update, context):
    query = update.callback_query
    types = {
        'config_c': configure_challenge,
        'user': configure_user,
    }
    try:
        type = query.data.split("|")[0]
        query.answer(types[type](query))
        logging.info(f"callback: {query.data} -> ✅")
    except:
        logging.exception(f"callback: {query} -> !!!")


if __name__ == "__main__":
    logging.basicConfig(format='%(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    warnings.filterwarnings("ignore",
                            message="Starting a Matplotlib GUI outside of the main thread will likely fail.")

    temp_lock = threading.Semaphore()

    MENU_OPTIONS = {
        "➕ New Prediction": select_country,
        "📊 My Predictions": user_predictions,
        "⚙ Preferences": preferences,
        "🏅 High Scores": high_scores,
        "ℹ About": about,
    }

    if constants.is_test_environment():
        token = constants.TEST_TOKEN
        logging.info("Starting with test token")
        test_environment = True
        DEBUG_SCORES = False
    else:
        token = constants.REAL_TOKEN
        logging.info("Starting with real token")
        test_environment = DEBUG_SCORES = False

    updater = Updater(token=token,
                      use_context=True,
                      workers=0)
    dispatcher = updater.dispatcher

    database = load_database(
        CPGameData({
            'scores_update': None,
            'users': dict(),
            'high_scores': [],
            'high_scores_daily': [],
            'groups': dict(),
            'challenges': dict(),
        })
    )
    upgrade_user_data(
        database['users'],
        {
            'chart_scale': 1.5,
            'high_scores_view': "total",
            'last_conversation_state': constants.MENU,
            'last_scheduled_update': None,
            'last_update': 0,
            'limits_note': False,
            'scheduled_updates_interval': None,
            'scores_daily': dict(),
            'update_notifications': True,
        }
    )

    update_database()

    conversation_states = {
        constants.MENU: [MessageHandler(Filters.text(MENU_OPTIONS.keys()), menu)],
        constants.GIVE_PREDICTION: [MessageHandler(Filters.text, give_prediction)],
        constants.CONFIRM_PREDICTION: [MessageHandler(Filters.photo, confirm_prediction),
                                       MessageHandler(Filters.text, give_prediction)],
        constants.LINK_ACCOUNT: [MessageHandler(Filters.text, link_account)],
        constants.DO_LINK: [MessageHandler(Filters.text, do_link)],
        constants.CUSTOM_NICKNAME: [MessageHandler(Filters.text, custom_nickname)],
        constants.CHANGE_PREFERENCES: [MessageHandler(Filters.text, change_preferences)],
        constants.COUNTRY_DETAILS: [MessageHandler(Filters.text, country_details)],
        constants.HIGH_SCORES: [MessageHandler(Filters.text, high_scores)]
    }

    dispatcher.add_handler(MessageHandler(Filters.regex(constants.SECRET_REGEX),
                                          lambda *a: constants.secret_function(*a, updater)))
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("settings", preferences))
    dispatcher.add_handler(CommandHandler("help", help_))

    dispatcher.add_handler(CommandHandler("7dayschallenge",
                                          lambda *a: group_challenge(*a, duration=datetime.timedelta(days=7))))
    dispatcher.add_handler(CommandHandler("30dayschallenge",
                                          lambda *a: group_challenge(*a, duration=datetime.timedelta(days=30))))
    dispatcher.add_handler(CommandHandler("100dayschallenge",
                                          lambda *a: group_challenge(*a,
                                                                     duration=datetime.timedelta(days=100))))
    dispatcher.add_handler(CommandHandler("oneyearchallenge",
                                          lambda *a: group_challenge(*a,
                                                                     duration=datetime.timedelta(days=365))))

    dispatcher.add_handler(CallbackQueryHandler(handle_callback))

    dispatcher.add_handler(MessageHandler(Filters.all, handle_message))

    for challenge_id_ in database['challenges'].keys():
        set_challenge_updater(challenge_id_)
    # noinspection PyTypeChecker
    signal(SIGINT, backup_database)
    # noinspection PyTypeChecker
    signal(SIGTERM, backup_database)
    updater.start_polling()

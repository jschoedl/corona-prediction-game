import datetime
import logging
import multiprocessing
import os
import random
import time
import warnings
from copy import copy
from signal import signal, SIGTERM, SIGINT
from threading import Semaphore

import compress_pickle
import requests
from matplotlib.dates import num2date
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ChatAction
from telegram.error import Unauthorized
from telegram.ext import CommandHandler, MessageHandler, Filters, ConversationHandler, Updater

import charts
import eastereggs
import internal
import line_detection
from data import Data
from scores import get_score, get_daily


def async_(fun):
    return fun
    # return lambda *args, **kwargs: dispatcher.run_async(fun, *args, **kwargs)


def load_database(base: dict):
    if not test_environment:
        params = {
            'api_dev_key': internal.API_DEV_KEY,
            'api_option': "list",
            'api_user_key': internal.API_USER_KEY,
        }
        res = requests.post(f"https://pastebin.com/api/api_post.php", data=params)
        paste_key = str(res.content)[
                    str(res.content).rindex("<paste_key>") + 11:str(res.content).rindex(
                        "</paste_key>")]

        params = {
            'api_dev_key': internal.API_DEV_KEY,
            'api_option': "show_paste",
            'api_user_key': internal.API_USER_KEY,
            'api_paste_key': paste_key,
        }
        res = requests.post(f"https://pastebin.com/api/api_raw.php", data=params)
        with open(internal.DATABASE_PATH, "wb") as f:
            f.write(res.content)

    if not test_environment or test_environment and os.path.exists(internal.DATABASE_PATH):
        _database = compress_pickle.load(internal.DATABASE_PATH)
        _database = multiprocessing.Manager().dict(_database)
        logging.info(f"Loaded database from {internal.DATABASE_PATH}.")
        for param, value in base.items():
            if param not in _database:
                _database[param] = value
                logging.info(
                    f"Parameter {param} was not in the database. The default value has been set.")
        return _database

    else:
        logging.info(f"No backup found.")
        return base


def backup_database(*args):
    compress_pickle.dump(dict(database), internal.DATABASE_PATH)

    if not test_environment:
        with open(internal.DATABASE_PATH, "rb") as f:
            updater.bot.send_document(
                chat_id=internal.ADMIN_USER,
                document=f,
            )
        if args:
            try:
                params = {
                    'api_dev_key': internal.API_DEV_KEY,
                    'api_option': "list",
                    'api_user_key': internal.API_USER_KEY,
                }
                res = requests.post(f"https://pastebin.com/api/api_post.php", data=params)
                paste_key = str(res.content)[
                            str(res.content).index("<paste_key>") + 11:str(res.content).index(
                                "</paste_key>")]

                params = {
                    'api_dev_key': internal.API_DEV_KEY,
                    'api_option': "delete",
                    'api_user_key': internal.API_USER_KEY,
                    'api_paste_key': paste_key,
                }
                requests.post(f"https://pastebin.com/api/api_post.php", data=params)
            except ValueError:
                logging.info("No old backup found.")
            else:
                logging.info("deleted old database")
            with open(internal.DATABASE_PATH, "rb") as f:
                params = {
                    'api_dev_key': internal.API_DEV_KEY,
                    'api_option': "paste",
                    'api_paste_code': f.read(),
                    'api_user_key': internal.API_USER_KEY,
                    'api_paste_private': 2,
                }
                requests.post(f"https://pastebin.com/api/api_post.php", data=params)

    logging.info(f"Backed up database at {internal.DATABASE_PATH}.")
    if args:
        updater.stop()


def get_flag(country):
    for label in SUPPORTED_COUNTRIES:
        if label[3:] == country:
            return label[:2]
    logging.error(f"The country {country} is not supported.")
    return "  "


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


def log(fun):
    def fun_with_log(update, context):
        if update.message.chat.type != "private":
            return

        user = update.message.from_user
        try:
            conversation_state = fun(update, context)
            logging.info("%s: %s -> %s", user.username, update.message.text,
                         conversation_state)
            if isinstance(conversation_state, int):
                database['users'][user.id]['last_conversation_state'] = conversation_state
            return conversation_state
        except:
            logging.info("%s: %s -> !!!", user.username, update.message.text)
            raise

    return fun_with_log


@log
def start(update, _):
    send_menu_markup("Welcome to the Corona Prediction Game!", update)

    global database
    user_id = update.message.from_user.id
    if user_id not in database['users']:
        database['users'][user_id] = {
            'drawing_area': None,  # type: tuple
            'drawing_update': None,  # type: datetime.date
            'high_scores_view': None,
            'last_conversation_state': None,  # type: int
            'last_scheduled_update': None,
            'last_update': list(UPDATES.keys())[-1],
            'limits_note': False,
            'nickname': "<hidden>",
            'nickname_confirmed': False,
            'predictions': dict(),
            'recent_prediction': dict(),
            'recent_country': "",
            'scheduled_updates_interval': None,
            'scores': dict(),
            'update_notifications': True,
        }

    if update.message.from_user.id == internal.ADMIN_USER:
        backup_database()
    return MENU


@log
def menu(update, context):
    return MENU_OPTIONS[update.message.text](update, context)


def select_country(update, _):
    markup = [[SUPPORTED_COUNTRIES[0]]]
    for i in range(0, len(SUPPORTED_COUNTRIES[1:]) * 3, 3):
        markup.append(SUPPORTED_COUNTRIES[i + 1:i + 4])

    update.message.reply_text("Please select a country.",
                              reply_markup=ReplyKeyboardMarkup(
                                  markup,
                                  one_time_keyboard=True
                              ))
    return GIVE_PREDICTION


@log
@async_
def give_prediction(update, _):
    if update.message.text not in SUPPORTED_COUNTRIES:
        markup = [[SUPPORTED_COUNTRIES[0]]]
        for i in range(0, len(SUPPORTED_COUNTRIES[1:]) * 3, 3):
            markup.append(SUPPORTED_COUNTRIES[i + 1:i + 4])
        update.message.reply_text(
            text="Please select a country from the markup keyboard. If you cannot see the country list, tap on the symb"
                 "ol with four squares on the right side next to the message field.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=markup,
                one_time_keyboard=True
            )
        )
        return GIVE_PREDICTION

    global database
    country = update.message.text[3:]
    user_id = update.message.from_user.id
    user_data = database['users'][user_id]

    # noinspection PyTypeChecker
    updater.bot.send_chat_action(user_id, ChatAction.UPLOAD_PHOTO)

    database['users'][user_id]['recent_country'] = country
    force = not (
            database['users'][user_id]['drawing_area'] and
            database['users'][user_id]['drawing_update'] == datetime.date.today()
    )
    res = charts.visualize_for_input(country, covid_stats, force=force)
    if res:
        database['users'][user_id]['drawing_area'] = res
        database['users'][user_id]['drawing_update'] = datetime.date.today()

    if country in user_data['predictions'].keys():
        warning = f"\n\n⚠ You already gave a prediction for this country. If you continue, it will be deleted and the" \
                  f" score will be 0 again."
    else:
        warning = ""

    with open(f"{charts.IMAGES_PATH}/{country}.jpg", "rb") as f:
        update.message.reply_photo(
            photo=f,
            caption=f"📈Alright, here are the daily new cases of Covid-19 "
                    f"{'for the whole' if country == 'World' else 'in'} {country}. How will the pandemic continue?\n\n"
                    "Download the image and draw your estimate with the Telegram app or a software of your choice. Then"
                    " upload the edited image in this chat. Your drawn line will be detected automatically!"
                    "\n\n Use /start to go back." + warning,
            reply_markup=ReplyKeyboardRemove()
        )
    return CONFIRM_PREDICTION


@log
@async_
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
        file.download(custom_path=internal.TEMP_PATH)
        raw_predictions = line_detection.evaluate(internal.TEMP_PATH, country, drawing_area, covid_stats)
        if type(raw_predictions) == str:
            update.message.reply_text(raw_predictions)
            return CONFIRM_PREDICTION
        database['users'][user_id]['recent_prediction'] = raw_predictions
        charts.visualize_for_confirmation(country, raw_predictions, internal.TEMP_PATH, covid_stats)
        with open(internal.TEMP_PATH, "rb") as f:
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
    return LINK_ACCOUNT


@log
def link_account(update, _):
    global database
    user_id = update.message.from_user.id

    if "no" in update.message.text.lower():
        update.message.reply_text(
            text="🔄 If you want to, you can send the picture again. At any time, /start can be used to get back to the "
                 "menu.",
            reply_markup=ReplyKeyboardRemove()
        )
        return CONFIRM_PREDICTION

    elif "right" in update.message.text.lower() or "yes" in update.message.text.lower():
        database['users'][user_id]['predictions'][
            database['users'][user_id]['recent_country']] = \
            database['users'][user_id]['recent_prediction']
        database['users'][user_id]['scores'][
            database['users'][user_id]['recent_country']] = 0
        if database['users'][user_id]['nickname_confirmed']:
            send_menu_markup("✅ Cool, your estimate has been saved.", update)
            return MENU

        update.message.reply_text(
            text="Cool, right now you officially participated in the Corona Prediction Game. Your Performance might be "
                 "shown to everyone in the High Score section. How do you want to appear there?",
            reply_markup=ReplyKeyboardMarkup(
                [[f"Link my username (@{update.message.from_user.username})"],
                 ["Use a custom nickname"], ["Keep my identity hidden"]],
                one_time_keyboard=True
            )
        )
        return DO_LINK
    else:
        update.message.reply_text(
            text="🧐 Sorry, does this image represent your estimate? Use /start to abort and get to the main menu.",
            reply_markup=ReplyKeyboardMarkup(
                [["✅ Yes, Continue"], ["⏪ No, Go Back"]],
                one_time_keyboard=True
            )
        )
        return LINK_ACCOUNT


@log
def do_link(update, context):
    global database
    user_id = update.message.from_user.id

    if "username" in update.message.text.lower():
        database['users'][user_id]['nickname'] = f"@{update.message.from_user.username}"
        database['users'][user_id]['nickname_confirmed'] = True
        send_menu_markup("✅ Your choice was saved.", update)
        return MENU
    elif "hidden" in update.message.text.lower():
        database['users'][user_id]['nickname'] = "<hidden>"
        database['users'][user_id]['nickname_confirmed'] = True
        send_menu_markup("✅ Your choice was saved.", update)
        return MENU
    elif "nickname" in update.message.text.lower():
        update.message.reply_text(
            text="Please enter your custom nickname now.",
            reply_markup=ReplyKeyboardRemove()
        )
        return CUSTOM_NICKNAME
    else:
        return custom_nickname(update, context)


@log
def custom_nickname(update, _):
    if len(new_nickname := update.message.text) > 30:
        update.message.reply_text(
            text="This nickname is pretty long - Please keep it below 30 characters. And again: What shall be your "
                 "name in the High Scores section? You can use /start to go back to the menu at any time.",
            reply_markup=ReplyKeyboardRemove()
        )
        return CUSTOM_NICKNAME

    global database
    user_id = update.message.from_user.id
    database['users'][user_id]['nickname'] = new_nickname
    database['users'][user_id]['nickname_confirmed'] = True

    send_menu_markup("✅ Your choice was saved.", update)
    return MENU


def preferences(update, _):
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
    return CHANGE_PREFERENCES


@log
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
        return DO_LINK
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

    highscores = []
    for user in database['users'].values():
        for country, score in user['scores'].items():
            if daily:
                timespan = database['scores_update'] - num2date(
                    list(user['predictions'][country].keys())[0]).date()
                included_days = timespan.days + 1
                score = score / included_days if included_days else 0
            highscores.append((score, user, country))
    highscores.sort(reverse=True, key=lambda x: x[0])

    formatted_highscores = []
    user_id = update.message.from_user.id
    for i, (score, user, country) in enumerate(highscores):
        if user == database['users'][user_id]:
            formatted_highscores.append(
                f"#{i + 1} {get_flag(country)} {score:.3f}: {user['nickname']} <-- you")
        elif i < 10:
            formatted_highscores.append(
                f"#{i + 1} {get_flag(country)} {score:.3f}: {user['nickname']}")

    if daily:
        response = "Average Daily Score\n\n"
    else:
        response = "Total Scores\n\n"
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
    return HIGH_SCORES


def about(update, _):
    send_menu_markup("This is version 1.5.0. \nChangelog: @cpgame_changelog\nGitHub: "
                     "https://github.com/jschoedl/corona-prediction-game\n\n"
                     "This bot is using a dataset maintained by 'Our World in Data'. You can find it "
                     "here: https://github.com/owid/covid-19-data/tree/master/public/data\n\n"
                     "The original data is provided by the European Centre for Disease Prevention and Control (EDCD). "
                     "For more information on their copyright policy, check out this link: "
                     "https://www.ecdc.europa.eu/en/copyright\n\nThe idea for this bot was inspired by @reispflanze, "
                     "who also designed its logo. The bot itself was written in Python by me, @Jakob_Schoedl. Do not "
                     "hesitate to contact me with your feedback, bugs and problems!", update)
    return MENU


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
        return COUNTRY_DETAILS
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
        return COUNTRY_DETAILS


@log
@async_
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
            charts.visualize([country, country], [country_predictions, country_predictions], internal.TEMP_PATH,
                             covid_stats, titles=[f"Daily reported Covid-19-infections "
                                                  f"{'for the whole' if country == 'World' else 'in'} {country}", ""],
                             offsets=[[300, 300], [10, 10]])
            with open(internal.TEMP_PATH, "rb") as f:
                update.message.reply_photo(
                    photo=f
                )
        finally:
            temp_lock.release()
        return COUNTRY_DETAILS
    else:
        fancy_error(update, context)


@log
def unknown_outside_conversation(update, context):
    if state := database['users'][update.message.from_user.id]['last_conversation_state']:
        for handler in conversation_states[state]:
            if handler.check_update(update):
                return handler.callback(update, context)
        else:
            fancy_error(update, context)
            return

    fancy_error(update, context, internal_error=True)


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
            text=eastereggs.SECRET_ERROR
        )
        return

    if type_error:
        to_append = "\nPlease select an option from the markup keyboard! Just tap on the icon on the right side next " \
                    "to the text box."
    elif internal_error:
        to_append = "This is an internal error and (probably) not your fault."
    else:
        to_append = ""

    if internal_error:
        markup = ReplyKeyboardMarkup([["/start"]])
    else:
        markup = None
    update.message.reply_text(
        text=f"{random.choice(first)}, {random.choice(second)}{' type' if type_error else ''} {random.choice(third)}. "
             f"{to_append}",
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
                user_data[param] = standard
                logging.info(
                    f"Parameter {param} not found for user {user_id}, added default value.")
        users[user_id] = user_data


def update_database(database: dict, covid_stats: Data, test_environment: bool, temp_lock: Semaphore, updater: Updater):
    """
    Download new Covid-19-statistics and send special types of notifications every 24h.
    This function is called as multiprocessing.Process.
    """
    while True:
        # download new statistics
        logging.info(f"last scores update: {database['scores_update']}")
        if database['scores_update'] != datetime.datetime.now().date():
            logging.info("updating..")
            for user_id, user_data in database['users'].items():
                for country, prediction in user_data['predictions'].items():
                    user_data['scores'][country] = get_score(country, covid_stats, get_daily(prediction))
            database['scores_update'] = datetime.datetime.now().date()
            print(database['scores_update'])

        # send pending messages
        users = database['users']
        for user_id, user_data in copy(users).items():
            # update notifications
            if (not test_environment and user_data['update_notifications']) or user_id == internal.ADMIN_USER:
                for update_id, text in UPDATES.items():
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
            if user_id in users and ((not test_environment and user_data['scheduled_updates_interval']) or
                                     user_id == internal.ADMIN_USER):
                if not user_data['last_scheduled_update']:
                    logging.error(
                        f"No last scheduled update interval set for user {user_id}.")
                else:
                    if datetime.date.today() - user_data['last_scheduled_update'] >= \
                            user_data['scheduled_updates_interval']:
                        try:
                            # noinspection PyTypeChecker
                            updater.bot.send_chat_action(user_id, ChatAction.UPLOAD_PHOTO)

                            greetings = (
                                "Hi there", "Hey there", "Hello there", "Hi", "Hey", "Hello",
                                "What's up",
                                "Cheers", "Woohoo")
                            if not user_data['limits_note']:
                                note = " Due to limitations of Telegram, I have to send it as a document."
                                user_data['limits_note'] = True
                            else:
                                note = ""
                            temp_lock.acquire()
                            charts.visualize(user_data['predictions'].keys(), user_data['predictions'].values(),
                                             internal.TEMP_PATH, covid_stats)
                            # send uncompressed
                            with open(internal.TEMP_PATH, "rb") as f:
                                updater.bot.send_document(
                                    chat_id=user_id,
                                    document=f,
                                    caption=f"{random.choice(greetings)}, here is your prediction report!{note}"
                                )
                            user_data['last_scheduled_update'] = datetime.date.today()
                        except Unauthorized:
                            try:
                                del users[user_id]
                                logging.info(f"Removed user {user_id}")
                            except:
                                logging.error(f"Could not remove {user_id}")
                        finally:
                            temp_lock.release()
        now = datetime.datetime.now()
        tomorrow = datetime.datetime(now.year, now.month, now.day + 1)
        logging.info(f"next database update: {(tomorrow - now)}")
        time.sleep((tomorrow - now).total_seconds())


if __name__ == "__main__":
    logging.basicConfig(format='%(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    warnings.filterwarnings("ignore", message="Starting a Matplotlib GUI outside of the main thread will likely fail.")

    SUPPORTED_COUNTRIES = [
        "🗺️ World",
        "🇦🇫 Afghanistan",
        "🇩🇿 Algeria",
        "🇦🇲 Armenia",
        "🇦🇺 Australia",
        "🇦🇹 Austria",
        "🇦🇿 Azerbaijan",
        "🇧🇭 Bahrain",
        "🇧🇾 Belarus",
        "🇧🇪 Belgium",
        "🇧🇷 Brazil",
        "🇰🇭 Cambodia",
        "🇨🇦 Canada",
        "🇨🇳 China",
        "🇭🇷 Croatia",
        "🇨🇿 Czech Republic",
        "🇩🇰 Denmark",
        "🇩🇴 Dominican Republic",
        "🇪🇨 Ecuador",
        "🇪🇬 Egypt",
        "🇪🇪 Estonia",
        "🇫🇮 Finland",
        "🇫🇷 France",
        "🇬🇪 Georgia",
        "🇩🇪 Germany",
        "🇬🇷 Greece",
        "🇮🇸 Iceland",
        "🇮🇳 India",
        "🇮🇩 Indonesia",
        "🇮🇷 Iran",
        "🇮🇶 Iraq",
        "🇮🇪 Ireland",
        "🇮🇱 Israel",
        "🇮🇹 Italy",
        "🇯🇵 Japan",
        "🇰🇼 Kuwait",
        "🇱🇧 Lebanon",
        "🇱🇹 Lithuania",
        "🇱🇺 Luxembourg",
        "🇲🇰 Macedonia",
        "🇲🇾 Malaysia",
        "🇲🇽 Mexico",
        "🇲🇨 Monaco",
        "🇳🇵 Nepal",
        "🇳🇱 Netherlands",
        "🇳🇿 New Zealand",
        "🇳🇬 Nigeria",
        "🇳🇴 Norway",
        "🇴🇲 Oman",
        "🇵🇰 Pakistan",
        "🇵🇭 Philippines",
        "🇶🇦 Qatar",
        "🇷🇴 Romania",
        "🇷🇺 Russia",
        "🇸🇲 San Marino",
        "🇸🇬 Singapore",
        "🇰🇷 South Korea",
        "🇪🇸 Spain",
        "🇱🇰 Sri Lanka",
        "🇸🇪 Sweden",
        "🇨🇭 Switzerland",
        "🇹🇼 Taiwan",
        "🇹🇭 Thailand",
        "🇦🇪 United Arab Emirates",
        "🇬🇧 United Kingdom",
        "🇺🇸 United States",
        "🇻🇳 Vietnam",
    ]
    UPDATES = {
        1: "Hey there, High Scores are now unlocked! If you do not want to receive any more messages on major updates, "
           "check out the new notification setting in the Preferences.\n\nNow, there is also a Changelog available: "
           "@cpgame_changelog",
        2: "Hi everyone, now you can schedule daily or weekly updates containing a summary of your predictions in the "
           "settings!\n\nYou can disable these notifications in the settings as well. For more detailed information on "
           "new features, check out the Changelog: @cpgame_changelog",
    }

    MENU = 1

    GIVE_PREDICTION = 21
    CONFIRM_PREDICTION = 22
    LINK_ACCOUNT = 23
    DO_LINK = 24
    CUSTOM_NICKNAME = 240

    COUNTRY_DETAILS = 32

    CHANGE_PREFERENCES = 41

    HIGH_SCORES = 50

    PROCESS_UNKNOWN = 61

    MENU_OPTIONS = {
        "➕ New Prediction": select_country,
        "📊 My Predictions": user_predictions,
        "⚙ Preferences": preferences,
        "🏅 High Scores": high_scores,
        "ℹ About": about,
    }

    if internal.is_test_environment():
        token = internal.TEST_TOKEN
        logging.info("Starting with test token")
        test_environment = True
        DEBUG_SCORES = False
    else:
        token = internal.REAL_TOKEN
        logging.info("Starting with real token")
        test_environment = DEBUG_SCORES = False

    updater = Updater(token=token,
                      use_context=True)
    dispatcher = updater.dispatcher
    temp_lock = Semaphore()
    covid_stats = Data()

    database = load_database(
        base=multiprocessing.Manager().dict({
            'scores_update': None,
            'users': dict(),
        }),
    )
    upgrade_user_data(
        database['users'],
        {
            'high_scores_view': "total",
            'last_conversation_state': None,
            'last_scheduled_update': None,
            'last_update': 0,
            'limits_note': False,
            'scheduled_updates_interval': None,
            'update_notifications': True,
        }
    )

    multiprocessing.Process(
        target=update_database,
        args=(database, covid_stats, test_environment, temp_lock, updater),
    ).start()

    conversation_states = {
        MENU: [MessageHandler(Filters.text(MENU_OPTIONS.keys()), menu)],
        GIVE_PREDICTION: [MessageHandler(Filters.text, give_prediction)],
        CONFIRM_PREDICTION: [MessageHandler(Filters.photo, confirm_prediction)],
        LINK_ACCOUNT: [MessageHandler(Filters.text, link_account)],
        DO_LINK: [MessageHandler(Filters.text, do_link)],
        CUSTOM_NICKNAME: [MessageHandler(Filters.text, custom_nickname)],
        CHANGE_PREFERENCES: [MessageHandler(Filters.text, change_preferences)],
        COUNTRY_DETAILS: [MessageHandler(Filters.text, country_details)],
        HIGH_SCORES: [MessageHandler(Filters.text, log(high_scores))]
    }

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start),
                      MessageHandler(Filters.regex(eastereggs.SECRET_REGEX),
                                     log(lambda *a: eastereggs.secret_function(*a, updater))),
                      MessageHandler(Filters.text, unknown_outside_conversation)],
        states=conversation_states,
        fallbacks=[MessageHandler(Filters.all, log(invalid_type))],
        allow_reentry=True,
    )
    dispatcher.add_handler(conversation_handler)

    # noinspection PyTypeChecker
    signal(SIGINT, backup_database)
    # noinspection PyTypeChecker
    signal(SIGTERM, backup_database)
    updater.start_polling()

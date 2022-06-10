# Corona Prediction Game
## ~~Try it out!~~
~~Telegram: [@cpgame_bot](https://t.me/cpgame_bot)~~

> After the Corona Prediction Game had been online for about 1.5 years and users had made more than 400 predictions, I decided to shut it down in May 2022. It turned out that the code didn't scale well with so many users. Feel free to reuse what you need, but note that I wasn't an overly experienced programmer when I developed this bot.

## About
Users of this bot can predict the Covid-19 statistics by drawing a graph into a diagram. Afterwards, the number of cases is compared with the prediction and for every predicted day, up to 1 point can be scored.

This bot is using a dataset maintained by 'Our World in Data'. You can find it [here](https://github.com/owid/covid-19-data/tree/master/public/data). The original data is provided by the European Centre for Disease Prevention and Control (EDCD). For more information on their copyright policy, check out [this link](https://www.ecdc.europa.eu/en/copyright).

## Running locally
Due to the use of the library ```multiprocessing``` errors might occur when running on Windows. I did not test it though.
1. Install the dependencies: ```pip install -r requirements.txt```
2. Create a new Telegram bot using [@BotFather](https://t.me/BotFather)
3. Insert the bot token at internals.py
4. Run the script: ```python main.py```

## Data structures

### database

- scores_update: datetime.datetime
- users: dict
    - (user id): int
        - chart_scale: float
        - drawing_area: tuple
        - drawing_update: datetime.date
        - high_scores_view: str
        - last_conversation_state: int
        - last_scheduled_update: datetime.datetime
        - last_update: int
        - limits_note: bool
        - nickname: str
        - nickname_confirmed: False
        - predictions: dict
        - recent_prediction: dict
        - recent_country: str
        - scheduled_updates_interval: None
        - scores: dict
        - scores_daily: dict
        - scores_persistent: dict
        - persistency_notification_sent: list
            - (country name): str
        - update_notifications: bool
- high_scores: list
- high_scores_daily: list
- high_scores_yesterday: list
- groups: dict
    - (chat id):int
        - configurations: dict
            - (config ids): int
                - bets: dict
                - country: str
                - duration: datetime.timedelta
                - submissions: str
                - user: int
- challenges: dict
    - (challenge id): int
        - bets: dict
        - chat_id: int
        - country: str
        - duration: datetime.timedelta
        - end: datetime.date
        - id: int
        - message_id: int
        - submissions: str
        - submission_end: datetime.datetime
        - user: int

### context.user_data

- action: str
- challenge_active: bool
- challenge_id: int
- chat_id: int
- config_id: int

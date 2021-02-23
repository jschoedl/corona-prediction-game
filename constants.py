############################
# Basic Setup
############################

# Telegram Bot Token (Get a new one from @BotFather)
TEST_TOKEN = "1329741940:AAEe7DR7OcNLMod_11usCN7bYOV9MwuWC6U"

TEMP_PATH = ".temp.jpg"
DATABASE_PATH = "database.gz"


def is_test_environment():
    return len(s := __file__.split("/")) > 2 and s[2] == "jakob"


# You can leave the following parameters unfilled if you keep running in the test environment.

REAL_TOKEN = "1330487511:AAHftSuTgG92r-JHK9HqftoPo7rhn5YNI18"

# Telegram chat with the administrator
ADMIN_USER = 598790891

# API keys for backups
DROPBOX_TOKEN = "6MYiyFqUOCoAAAAAAAAAAV6VRMbT-myRD-TwaYg9VBk4h5ZQlMO80otTvwawFpY5"
DROPBOX_PATH = "/database.gz"

############################
# Statistics and Charts
############################

TEMP_DIR = ".covid_data"
CSV_SOURCE = "https://covid.ourworldindata.org/data/owid-covid-data.csv"
IMAGES_PATH = ".covid_images"
N_PREDICTED_DAYS = 150
LINE_THRESHOLD = 0.8

############################
# Conversation Structure and Countries
############################

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

UPDATES = {
    1: "Hey there, High Scores are now unlocked! If you do not want to receive any more messages on major updates, "
       "check out the new notification setting in the Preferences.\n\nNow, there is also a Changelog available: "
       "@cpgame_changelog",
    2: "Hi everyone, now you can schedule daily or weekly updates containing a summary of your predictions in the "
       "settings!\n\nYou can disable these notifications in the settings as well. For more detailed information on "
       "new features, check out the Changelog: @cpgame_changelog",
}

SUPPORTED_COUNTRIES = [
    "🗺️ World",
    "🇦🇫 Afghanistan",
    "🇦🇱 Albania",
    "🇩🇿 Algeria",
    "🇦🇩 Andorra",
    "🇦🇴 Angola",
    "🇦🇮 Anguilla",
    "🇦🇬 Antigua & Barbuda",
    "🇦🇷 Argentina",
    "🇦🇲 Armenia",
    "🇦🇺 Australia",
    "🇦🇹 Austria",
    "🇦🇿 Azerbaijan",
    "🇧🇸 Bahamas",
    "🇧🇭 Bahrain",
    "🇧🇩 Bangladesh",
    "🇧🇧 Barbados",
    "🇧🇾 Belarus",
    "🇧🇪 Belgium",
    "🇧🇿 Belize",
    "🇧🇯 Benin",
    "🇧🇲 Bermuda",
    "🇧🇹 Bhutan",
    "🇧🇴 Bolivia",
    "🇧🇦 Bosnia and Herzegovina",
    "🇧🇼 Botswana",
    "🇧🇷 Brazil",
    "🇧🇳 Brunei",
    "🇧🇬 Bulgaria",
    "🇧🇫 Burkina Faso",
    "🇧🇮 Burundi",
    "🇰🇭 Cambodia",
    "🇨🇲 Cameroon",
    "🇨🇦 Canada",
    "🇮🇨 Canary Islands",
    "🇨🇻 Cape Verde",
    "🇰🇾 Cayman Islands",
    "🇨🇫 Central African Republic",
    "🇹🇩 Chad",
    "🇨🇱 Chile",
    "🇨🇳 China",
    "🇨🇴 Colombia",
    "🇰🇲 Comoros",
    "🇨🇬 Congo",
    "🇨🇷 Costa Rica",
    "🇨🇮 Cote d’Ivoire",
    "🇭🇷 Croatia",
    "🇨🇺 Cuba",
    "🇨🇾 Cyprus",
    "🇨🇿 Czechia",
    "🇨🇩 Democratic Republic of Congo",
    "🇩🇰 Denmark",
    "🇩🇬 Diego Garcia",
    "🇩🇯 Djibouti",
    "🇩🇲 Dominica",
    "🇩🇴 Dominican Republic",
    "🇪🇨 Ecuador",
    "🇪🇬 Egypt",
    "🇸🇻 El Salvador",
    "🇬🇶 Equatorial Guinea",
    "🇪🇷 Eritrea",
    "🇪🇪 Estonia",
    "🇸🇿 Eswatini",
    "🇪🇹 Ethiopia",
    "🇫🇴 Faroe Islands",
    "🇫🇯 Fiji",
    "🇫🇮 Finland",
    "🇫🇷 France",
    "🇬🇦 Gabon",
    "🇬🇲 Gambia",
    "🇬🇪 Georgia",
    "🇩🇪 Germany",
    "🇬🇭 Ghana",
    "🇬🇮 Gibraltar",
    "🇬🇷 Greece",
    "🇬🇱 Greenland",
    "🇬🇩 Grenada",
    "🇬🇹 Guatemala",
    "🇬🇬 Guernsey",
    "🇬🇳 Guinea",
    "🇬🇼 Guinea-Bissau",
    "🇬🇾 Guyana",
    "🇭🇹 Haiti",
    "🇭🇳 Honduras",
    "🇭🇰 Hong Kong",
    "🇭🇺 Hungary",
    "🇮🇸 Iceland",
    "🇮🇳 India",
    "🇮🇩 Indonesia",
    "🇮🇷 Iran",
    "🇮🇶 Iraq",
    "🇮🇪 Ireland",
    "🇮🇲 Isle of Man",
    "🇮🇱 Israel",
    "🇮🇹 Italy",
    "🇯🇲 Jamaica",
    "🇯🇵 Japan",
    "🇯🇪 Jersey",
    "🇯🇴 Jordan",
    "🇰🇿 Kazakhstan",
    "🇰🇪 Kenya",
    "🇽🇰 Kosovo",
    "🇰🇼 Kuwait",
    "🇰🇬 Kyrgyzstan",
    "🇱🇦 Laos",
    "🇱🇻 Latvia",
    "🇱🇧 Lebanon",
    "🇱🇸 Lesotho",
    "🇱🇷 Liberia",
    "🇱🇾 Libya",
    "🇱🇮 Liechtenstein",
    "🇱🇹 Lithuania",
    "🇱🇺 Luxembourg",
    "🇲🇬 Madagascar",
    "🇲🇼 Malawi",
    "🇲🇾 Malaysia",
    "🇲🇻 Maldives",
    "🇲🇱 Mali",
    "🇲🇹 Malta",
    "🇲🇭 Marshall Islands",
    "🇲🇷 Mauritania",
    "🇲🇺 Mauritius",
    "🇲🇽 Mexico",
    "🇫🇲 Micronesia (country)",
    "🇲🇩 Moldova",
    "🇲🇨 Monaco",
    "🇲🇳 Mongolia",
    "🇲🇪 Montenegro",
    "🇲🇸 Montserrat",
    "🇲🇦 Morocco",
    "🇲🇿 Mozambique",
    "🇲🇲 Myanmar",
    "🇳🇦 Namibia",
    "🇳🇵 Nepal",
    "🇳🇱 Netherlands",
    "🇳🇿 New Zealand",
    "🇳🇮 Nicaragua",
    "🇳🇪 Niger",
    "🇳🇬 Nigeria",
    "🇲🇰 North Macedonia",
    "🇳🇴 Norway",
    "🇴🇲 Oman",
    "🇵🇰 Pakistan",
    "🇵🇸 Palestine",
    "🇵🇦 Panama",
    "🇵🇬 Papua New Guinea",
    "🇵🇾 Paraguay",
    "🇵🇪 Peru",
    "🇵🇭 Philippines",
    "🇵🇱 Poland",
    "🇵🇹 Portugal",
    "🇶🇦 Qatar",
    "🇷🇴 Romania",
    "🇷🇺 Russia",
    "🇷🇼 Rwanda",
    "🇸🇭 Saint Helena",
    "🇰🇳 Saint Kitts and Nevis",
    "🇱🇨 Saint Lucia",
    "🇻🇨 Saint Vincent and the Grenadines",
    "🇼🇸 Samoa",
    "🇸🇲 San Marino",
    "🇸🇦 Saudi Arabia",
    "🇸🇳 Senegal",
    "🇷🇸 Serbia",
    "🇸🇨 Seychelles",
    "🇸🇱 Sierra Leone",
    "🇸🇬 Singapore",
    "🇸🇰 Slovakia",
    "🇸🇮 Slovenia",
    "🇸🇧 Solomon Islands",
    "🇸🇴 Somalia",
    "🇰🇷 South Korea",
    "🇸🇸 South Sudan",
    "🇪🇸 Spain",
    "🇱🇰 Sri Lanka",
    "🇸🇩 Sudan",
    "🇸🇷 Suriname",
    "🇸🇪 Sweden",
    "🇨🇭 Switzerland",
    "🇸🇾 Syria",
    "🇹🇼 Taiwan",
    "🇹🇯 Tajikistan",
    "🇹🇿 Tanzania",
    "🇹🇭 Thailand",
    "🇹🇱 Timor",
    "🇹🇬 Togo",
    "🇹🇹 Trinidad and Tobago",
    "🇹🇳 Tunisia",
    "🇹🇷 Turkey",
    "🇹🇨 Turks and Caicos Islands",
    "🇺🇬 Uganda",
    "🇺🇦 Ukraine",
    "🇦🇪 United Arab Emirates",
    "🇬🇧 United Kingdom",
    "🇺🇸 United States",
    "🇺🇾 Uruguay",
    "🇺🇿 Uzbekistan",
    "🇻🇺 Vanuatu",
    "🇻🇦 Vatican",
    "🇻🇪 Venezuela",
    "🇻🇳 Vietnam",
    "🇾🇪 Yemen",
    "🇿🇲 Zambia",
    "🇿🇼 Zimbabwe",
]

############################
# Easter Eggs
############################

SECRET_ERROR = ":)"
SECRET_REGEX = "a^"


def secret_function(update, context, updater):
    pass

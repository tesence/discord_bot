# Discord Bot

A Discord Bot based on asynchronous programming (asyncio)

- Notify twitch streams status
- Dab

## Create a Twitch account to get a twich token

Create a Twitch account: https://www.twitch.tv

Connect to twitch using the bot account and generate a chat token for the bot

https://www.twitchtools.com/chat-token

## Setup environment (Python 3.6+ required)

Requires 3.6 because:
* it uses `async` and `await`, only available for Python 3.5+
* it uses fstrings, only available for Python 3.6+

### Windows

	cd <project folder>
	virtualenv -p python3.6 .venv
	.venv/Script/pip.exe install -r requirements.txt


### Linux

	cd <project folder>
	virtualenv -p python3.6 .venv
	.venv/bin/pip install -r requirements.txt

## Create a database

Create a postgresSQL database. The tables will be generated automatically.


## Create a configuration file

Create the file ```discord_bot/etc/<configuration_file>.py``` and fill it as follow:

```
# cfg.py
# Configurations variables

# CLIENT
COMMAND_PREFIX = "!"
ADMIN_ROLES = <list of roles that have admin rights>
LOADED_EXTENSIONS = ["stream.setup" "dab"]
DISCORD_BOT_TOKEN = <discord bot token>

# TWITCH COG
TWITCH_API_URL = "https://api.twitch.tv/kraken"
TWITCH_API_ACCEPT = "application/vnd.twitchtv.v5+json"
TWITCH_API_CLIENT_ID = <twitch client id>
MIN_OFFLINE_DURATION = 60

# DAB COG
DAB_COOLDOWN = 120

# DATABASE
DB_HOST = <DB_HOST>
DB_PORT = <DB_PORT>
DB_NAME = <DB_NAME>
DB_USER = <DB_USER>
DB_PASSWORD = <DB_PASSWORD>
```
## Run the bot

In the project folder, run:

### Windows

	.venv/Script/python.exe main.py <configuration_file>


### Linux

	.venv/bin/python main.py <configuration_file>


## COGS

### Twitch

The Twitch cog allows you to track a list of streams.
When one of the streams goes online, the bot sends an embed message including the stream information (game, title, ...)

#### Commands

	# Display a list of the tracked streams
	!stream list

	# Add a stream in the tracked list
	!stream add <username>

	# Add a stream in the tracked list (the notification will include the tag @everyone)
	!stream everyone <username>

	# The notification will be sent the channel in which the command has been used

	# Remove a stream from the tracked list
	!stream remove <username>


#### How does it work ?

##### Track streams

When an user uses whether `!stream add` or `!stream everyone`,
the bot stores the twitch `username` as well as the discord channel information in which the command has been called.  Then, the bot requests Twitch the twitch `id` for this `username`. This `id` will be used to retrieve the stream status.

##### Retrieving stream status

The bot requests Twitch every X seconds using all the twitch `ids` previously added.

- If stream was previously offline and goes online, the bot sends a notification in the related discord channel
- If the stream was previously online and goes offline, the bot flags the stream as offline.

#### Troubleshooting

##### API request fails
The Twitch API returns a list of json object for each online stream.

If no stream is online, the API will return:
```
{'stream': [] }
```
 If the API call fails, the API will not return anything
```
None
```
 The bot then has to handle both of these case separately in order not to tag all the streams as offline. Otherwise, the bot will notify every stream again on the next successful API request.

##### Fake API responses

The Twitch API isn't implemented on an unique server. Depending on which server the bot requests, the response can differ.

When a stream goes offline, we can see something like this happen

 - An API server sees the stream as offline
 - Another API server still sees the stream online several seconds after it went offline

If the bot requests the first server, it will find that the stream just went offline. If the bot requests the second on the next API call, it will understand that the stream just went online again and notify it.

To avoid that, the bot will look at the date when the stream went offline.
If the API still returns that the stream is offline during the X next seconds, the bot tags it as offline. Otherwise it considers that the stream didn't really go offline.

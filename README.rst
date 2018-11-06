|logo|

|Python| |Codacy Badge| |Maintainability|

A Discord Bot based on the Python framework
`discord.py <https://github.com/Rapptz/discord.py>`__

**Features**:

-  Twitch stream notifications
-  Dab command
-  `Ori DE Randomizer <https://github.com/sigmasin/OriDERandomizer>`__ support

   -  Manage the randomizer community role
   -  Generate seeds within discord
   -  Generate logic helper links

Setup environment (Python 3.6+ required)
========================================

Requires 3.6 because:

-  it uses ``async`` and ``await``, only available for Python 3.5+
-  it uses fstrings, only available for Python 3.6+

Clone the repository
--------------------

::

   git clone https://github.com/tesence/GumoBot.git

Windows
-------

::

   cd <project folder>
   virtualenv -p python3.6 .venv
   .venv/Script/pip.exe install -r requirements.txt

Linux
-----

::

   cd <project folder>
   virtualenv -p python3.6 .venv
   .venv/bin/pip install -r requirements.txt

Create a database
=================

Create a postgresSQL database. The tables will be generated
automatically.

Create configuration files
==========================

Create a folder where you will store all the configuration files.

Create a first file ``config.yaml`` that will store all the unique bot
variables

.. code:: yaml

   COMMAND_PREFIX: "!"

   DISCORD_BOT_TOKEN: <discord bot token>
   TWITCH_API_CLIENT_ID: <twitch client id>

   DATABASE_CREDENTIALS:
     host: <DB_HOST>
     port: <DB_PORT>
     database: <DB_NAME>
     user: <DB_USER>
     password: <DB_PASSWORD>

A second file ``default.yaml`` that will store all the default values

.. code:: yaml

   EXTENSIONS:
    - "stream"
    - "dab"
    - "ori_rando_seedgen"
    - "ori_logic_helper"

And a file for each guild in which the bot needs to behave differently.
Allows to set variables that only exist at a guild level like admin
roles

.. code:: yaml

   GUILD_ID: <guild_id>

   ADMIN_ROLES:
    - "admin_role_1"
    - "admin_role_2"
    ...

   EXTENSIONS:
    - "<allowed cog>"
    - "<allowed cog>"
    ...

   RANDO_ROLE: "Looking For Rando"

These values will override the default ones for that specific guild.

Run the bot
===========

In the project folder, run:


Windows
-------

::

   .venv/Script/python.exe main.py --config-dir /path/to/your/config/folder --log-dir /path/to/the/log/folder


Linux
-----

::

   .venv/bin/python main.py --config-dir /path/to/your/config/folder --log-dir /path/to/the/log/folder

Commands
========

Twitch
------

The twitch stream support implements a system of notification. When a
stream is online, a notification is sent in every discord channel where
it has been tracked. By default, the notification is automatically
deleted when the stream is offline. To prevent the bot from deleting the
notification it is possible to set the variable
``AUTO_DELETE_OFFLINE_STREAMS`` to False. The notification will then
turn to grey when the stream is offline the bot will react to it with a
wastebasket emoji. The notification will be deleted if the bot owner or
a user with one of the roles listed in ``ADMIN_ROLES`` reacts to it
aswell.

::

   AUTO_DELETE_OFFLINE_STREAMS = False

Additional configuration variables

-  ``MIN_OFFLINE_DURATION`` Duration (in seconds) spent offline
   (according to the API) after which the stream is considered offline for
   the bot. It allows to avoid multiple notifications if the broadcaster
   has some internet issues.

   Recommended minimum value: ``60``

Here are the different commands:

::

   # Display a list of the tracked streams
   !stream list

   # Track several streams in the current channel
   !stream add <username>

   # Track several streams in the current channel (the notification will include the tag @here)
   !stream here <username>

   # Track several streams in the current channel (the notification will include the tag @everyone)
   !stream everyone <username>

   # Stop tracking some streams in the current channel
   !stream remove <username>

Dab
---

Pretty straight forward, type ``!dab <something>`` to disrespect

Ori DE Randomizer
-----------------

Seed generation
~~~~~~~~~~~~~~~

::

   !seed [list of options...]

Default seed flags: ``Standard,Clues,ForceTrees,balanced``

Optional arguments

-  presets: casual, standard, expert, master, hard, ohko, 0xp, glitched
-  modes: shards, limitkeys, clues, default
-  logic paths: normal, speed, dbash, extended, extended-damage, lure,
   speed-lure, lure-hard, dboost, dboost-light, dboost-hard, cdash,
   cdash-farming, extreme, timed-level, glitched
-  variations: forcetrees, entrance, hard, starved, ohko,
   nonprogressmapstones, 0xp, noplants, noteleporters
-  flags: tracking, verbose_paths, classic_gen, hard-path, easy-path

A seed name can be set using double quotes

|seedgen|

Logic helper link generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

   !logic [preset] [list of options...]

-  presets: casual, standard, expert, master, hard, ohko, 0xp, glitched
-  items: WallJump (WJ), ChargeFlame (CF), DoubleJump (DJ), Bash (BS),
   Stomp (ST), Glide (GL), Climb (CL), ChargeJump (CJ), Dash (DA),
   Grenade (GR), WaterVein (WV), GumonSeal (GS), Sunstone (SS), Health
   (HC), Energy (EC), Keystone (KS), Mapstone (MS), Water, Wind,
   GrottoTP, GroveTP, SwampTP, ValleyTP, SorrowTP, ForlornTP

.. note::

   Denote multiples by appending ``xN`` to it, without a space.

   **Examples**:

   ``!logic CJ KSx2 Mapstone``

   ``!logic expert Bash Grenade Energyx4``

Randomizer community role
~~~~~~~~~~~~~~~~~~~~~~~~~

A simple role command. The randomizer community role is used for members
who want to be pinged when someone is looking for playing a randomizer
seed, it allows people to easily opt in/out without having to ask a
moderator.

.. |logo| image:: img/logo.png?raw=true
   :class: align-center
.. |Python| image:: https://img.shields.io/badge/Python-3.6%2B-blue.svg
   :target: https://www.python.org/
.. |Codacy Badge| image:: https://api.codacy.com/project/badge/Grade/902886185fd2476dadab0cb1a4c4f3a9
   :target: https://app.codacy.com/app/tesence/discord_bot?utm_source=github.com&utm_medium=referral&utm_content=tesence/discord_bot&utm_campaign=Badge_Grade_Dashboard
.. |Maintainability| image:: https://api.codeclimate.com/v1/badges/e5874485dd3795f5e940/maintainability
   :target: https://codeclimate.com/github/tesence/discord_bot/maintainability
.. |seedgen| image:: img/seedgen.png?raw=True
   :class: align-center


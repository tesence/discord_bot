GumoBot
===========

|Python| |Codacy Badge| |Maintainability|

A Discord Bot based on the Python framework discord.py_

.. _discord.py: https://github.com/Rapptz/discord.py


**Features**:

- Twitch stream notifications
- Dab command
- Ori DE Randomizer support

  - Manage the randomizer community role
  - Generate seeds within discord
  - Generate logic helper links


Setup environment (Python 3.6+ required)
----------------------------------------

Requires 3.6 because:

- it uses ``async`` and ``await``, only available for Python 3.5+
- it uses fstrings, only available for Python 3.6+

Clone the repository
~~~~~~~~~~~~~~~~~~~~

::

    git clone https://github.com/tesence/discord_bot

Windows
~~~~~~~

::

    cd <project folder>
    virtualenv -p python3.6 .venv
    .venv/Script/pip.exe install -r requirements.txt

Linux
~~~~~

::

    cd <project folder>
    virtualenv -p python3.6 .venv
    .venv/bin/pip install -r requirements.txt

Create a database
-----------------

Create a postgresSQL database. The tables will be generated automatically.

Create configuration files
--------------------------

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

And a file for each guild in which the bot needs to behave differently. Allows
to set variables that only exist at a guild level like admin roles

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
-----------

In the project folder, run:

Windows
~~~~~~~

::

    .venv/Script/python.exe main.py --config-dir /path/to/your/config/folder --log-dir /path/to/the/log/folder

Linux
~~~~~

::

    .venv/bin/python main.py --config-dir /path/to/your/config/folder --log-dir /path/to/the/log/folder

Commands
--------

WIP

.. |Python| image:: https://img.shields.io/badge/Python-3.6%2B-blue.svg
   :target: https://www.python.org/
.. |Codacy Badge| image:: https://api.codacy.com/project/badge/Grade/902886185fd2476dadab0cb1a4c4f3a9
   :target: https://app.codacy.com/app/tesence/discord_bot?utm_source=github.com&utm_medium=referral&utm_content=tesence/discord_bot&utm_campaign=Badge_Grade_Dashboard
.. |Maintainability| image:: https://api.codeclimate.com/v1/badges/e5874485dd3795f5e940/maintainability
   :target: https://codeclimate.com/github/tesence/discord_bot/maintainability

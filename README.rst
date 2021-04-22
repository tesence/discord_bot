|logo|

|Python| |Codacy Badge| |Maintainability|

A Discord Bot based on the Python framework
`discord.py <https://github.com/Rapptz/discord.py>`__


.. contents:: Features
   :depth: 1

Ori DE Randomizer
=================

Seed generation
---------------

Generates seeds for the `randomizer of Ori and the Blind Forest: Definitive edition <https://www.orirando.com/quickstart>`__

|seedgen|

::

   !seed [list of options...]
   !daily [list of options...]



Logic helper link generation
----------------------------

Generates help links for the `randomizer of Ori and the Blind Forest: Definitive edition <https://www.orirando.com/quickstart>`__

|logic helper|

::

   !logic [preset] [list of options...]

Randomizer community role
-------------------------

A simple role command. The randomizer community role is used for members
who want to be pinged when someone is looking for playing a randomizer
seed, it allows people to easily opt in/out without asking a moderator.


Twitch Alerts
=============

- Sends a stream notification when the stream is live
- Edits the notification when the stream goes offline
- Deletes the old notifications to keep the channels clean

Live notification

|stream live|

Offline notification

|stream offline|

::

   # Display a list of the tracked streams
   !stream list

   # Track several streams in the current channel
   !stream add [user_logins...]

   # Track several streams in the current channel (the notification will include the tag @here)
   !stream here [user_logins...]

   # Track several streams in the current channel (the notification will include the tag @everyone)
   !stream everyone [user_logins...]

   # Stop tracking some streams in the current channel
   !stream remove [user_logins...]

Dab
===

Pretty straight forward, type ``!dab <something>`` to disrespect someone


Tag
===

A classic tag command

|tag|

::

   # Get the list of available tags
   !tag list

   # Use a tag
   !tag <code>

   # Create a tag
   !tag create <code> "<content>"

   # Delete a tag
   !tag delete <code>


.. |logo| image:: img/logo.png?raw=true
   :class: align-center
.. |Python| image:: https://img.shields.io/badge/Python-3.6%2B-blue.svg
   :target: https://www.python.org/
.. |Codacy Badge| image:: https://api.codacy.com/project/badge/Grade/902886185fd2476dadab0cb1a4c4f3a9
   :target: https://app.codacy.com/app/tesence/GumoBot?utm_source=github.com&utm_medium=referral&utm_content=tesence/GumoBot&utm_campaign=Badge_Grade_Dashboard
.. |Maintainability| image:: https://api.codeclimate.com/v1/badges/879b28b7e0aa2fefc510/maintainability
   :target: https://codeclimate.com/github/tesence/GumoBot/maintainability
.. |seedgen| image:: img/seedgen.png?raw=True
   :class: align-center
.. |logic helper| image:: img/logic_helper.png?raw=True
   :class: align-center
.. |stream live| image:: img/stream_live.png?raw=True
   :class: align-center
.. |stream offline| image:: img/stream_offline.png?raw=True
   :class: align-center
.. |tag| image:: img/tag.png?raw=True
   :class: align-center

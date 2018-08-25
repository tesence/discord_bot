from discord import colour, embeds

TWITCH_ICON_URL = "https://www.shareicon.net/download/2015/09/08/98061_twitch_512x512.png"


def get_field(embed, field_name):
    fields = [field for field in embed.fields if field.name == field_name]
    if fields:
        return fields[0]


def get_notification(stream, everyone=False):
    """Return a message and an embed for a given stream

    :param stream: stream status
    :param everyone: Add '@everyone' in front of the message if True
    :return: notification message and embed
    """
    if stream.type == "live":
        message, embed = _get_stream_notification(stream)
    else:
        message, embed = _get_vodcast_notification(stream)

    if everyone:
        message = "@everyone " + message

    return message, embed


def get_offline_embed(embed):
    embed.colour = colour.Color.lighter_grey()
    return embed


def _get_stream_notification(stream):
    message = f"{stream.display_name} is streaming!"

    broadcast_type = "Stream"
    color = colour.Color.dark_purple()
    embed = _get_notification_embed(stream, broadcast_type, color)
    return message, embed


def _get_vodcast_notification(stream):
    message = f"{stream.display_name} started a vodcast!"

    broadcast_type = "Vodcast"
    color = colour.Color.red()
    embed = _get_notification_embed(stream, broadcast_type, color)
    return message, embed


def _get_notification_embed(stream, broadcast_type, color, *fields):
    """Get a live notification

    :param type: stream type
    :param color: embed color
    :return: notification message and embed
    """

    channel_url = f"https://www.twitch.tv/{stream.name}"

    embed = embeds.Embed()
    embed.colour = color

    embed.set_author(name=stream.display_name, url=channel_url, icon_url=TWITCH_ICON_URL)
    embed.description = channel_url

    embed.add_field(name="Title", value=stream.title, inline=False)
    embed.add_field(name="Game", value=stream.game, inline=False)
    embed.add_field(name="Type", value=broadcast_type)

    if stream.logo:
        embed.set_thumbnail(url=stream.logo)

    for field in fields:
        embed.add_field(**field)

    return embed


def get_stream_list_embed(streams_by_channel):
    """Build the embed to return on !stream list call

    :param streams_by_channel: dictionary
    {
      <discord_channel_1>: ["stream_name_1", "stream_name_2", ...]
      <discord_channel_2>: ["stream_name_2", "stream_name_3", ...]
      <discord_channel_3>: ["stream_name_1", "stream_name_3", ...]
    }
    :return: embed with the list of stream for each channel
    """
    embed = embeds.Embed()
    embed.set_author(name="Streams", icon_url=TWITCH_ICON_URL)
    for channel, streams in sorted(streams_by_channel.items(), key=lambda x: x[0].position):
        stream_links = [f"[{stream}](https://twitch.tv/{stream})" for stream in sorted(streams)]
        embed.add_field(name=channel.name, value=", ".join(stream_links), inline=False)
    return embed

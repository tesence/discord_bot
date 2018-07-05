from discord import colour, embeds

TWITCH_ICON_URL = "https://www.shareicon.net/download/2015/09/08/98061_twitch_512x512.png"
CLOCK_ICON_URL = "https://cdn2.iconfinder.com/data/icons/metro-uinvert-dock/256/Clock.png"


def get_field(embed, field_name):
    fields = [field for field in embed.fields if field.name == field_name]
    if fields:
        return fields[0]


def get_notification(status, everyone=False):
    """Return a message and an embed for a given stream

    :param status: stream status
    :param everyone: Add '@everyone' in front of the message if True
    :return: notification message and embed
    """
    if status['stream_type'] == "live":
        message, embed = _get_stream_notification(status)
    else:
        message, embed = _get_vodcast_notification(status)

    if everyone:
        message = "@everyone " + message

    return message, embed


def _get_stream_notification(status):
    message = f"{status['channel']['display_name']} is streaming!"

    broadcast_type = "Stream"
    color = colour.Color.dark_purple()
    embed = _get_notification_embed(status, broadcast_type, color, image=False)
    return message, embed


def _get_vodcast_notification(status):
    message = f"{status['channel']['display_name']} started a vodcast!"

    broadcast_type = "Vodcast"
    color = colour.Color.red()
    embed = _get_notification_embed(status, broadcast_type, color, image=False)
    return message, embed


def _get_notification_embed(data, broadcast_type, color, *fields, url=None,
                            image=True):
    """Get a live notification

    :param type: stream type
    :param color: embed color
    :return: notification message and embed
    """

    display_name = data['channel']['display_name']
    logo_url = data['channel']['logo']
    channel_url = data['channel']['url']
    if not url:
        url = channel_url
    title = data['channel']['status']
    game = data['game']
    image_url = data['preview']['large']

    embed = embeds.Embed()
    embed.colour = color

    embed.set_author(name=display_name, url=channel_url, icon_url=TWITCH_ICON_URL)
    embed.description = url

    embed.add_field(name="Title", value=title, inline=False)
    embed.add_field(name="Game", value=game, inline=False)
    embed.add_field(name="Type", value=broadcast_type)

    for field in fields:
        embed.add_field(**field)

    embed.set_footer(text="Stream live time", icon_url=CLOCK_ICON_URL)

    if image and image_url:
        embed.set_image(url=image_url)

    if logo_url:
        embed.set_thumbnail(url=logo_url)

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

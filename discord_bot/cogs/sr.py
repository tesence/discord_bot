import abc
import asyncio
import collections
import logging
import time

from discord import colour, embeds
from discord.ext import commands

import cfg
from discord_bot import utils
from discord_bot.utils import bold, underline


LOG = logging.getLogger('debug')

HEADERS = {
    "Accept": "application/json",
    "X-API-Key": cfg.SR_API_KEY
}


class SpeedrunData:

    __metaclass__ = abc.ABCMeta

    GAMES = {}
    CATEGORIES = {}
    RESOURCE_NAME = "unknown"

    @staticmethod
    @abc.abstractmethod
    def _get_game_id(elem):
        pass

    @staticmethod
    @abc.abstractmethod
    def _get_category_id(elem):
        pass

    @staticmethod
    @abc.abstractmethod
    def get_url(*args):
        pass

    @classmethod
    @abc.abstractmethod
    async def parse(cls, elem):
        pass

    @staticmethod
    def get_embed(summary):
        """ Build an embed
        :param summary: summary data to display
        :return: embed
        """
        FIELDS = ['place', 'time', 'url']

        embed = embeds.Embed()
        embed.colour = colour.Color.dark_gold()

        for game, categories in summary.items():
            value = ""
            for category, pb in categories.items():
                value += u"{category_name}:\n".format(category_name=underline(bold(category)))
                for field_name in set(pb.keys()) & set(FIELDS):
                    field_value = pb[field_name]
                    value += u"\t {field_name}: {field_value}\n".format(field_name=bold(field_name),
                                                                        field_value=field_value)
            embed.add_field(name=game, value=value)

        return embed

    @classmethod
    async def get_data(cls, url):
        begin = time.time()
        body, status_code = await utils.request(url, headers=HEADERS)
        if status_code == 200:
            data = body['data']
            LOG.debug("Request to {} successful ({:02.3f}s)".format(url, time.time() - begin))
            return data
        else:
            LOG.error("Cannot retrieve %ss: %s (http status %s)", cls.RESOURCE_NAME, status_code)

    @classmethod
    async def _get_game_name(cls, game_id):
        if game_id not in cls.GAMES:
            url = "{sr_api_url}/games/{game_id}".format(sr_api_url=cfg.SR_API_URL, game_id=game_id)
            game = await cls.get_data(url)
            cls.GAMES[game_id] = game['names']['international']
        return cls.GAMES[game_id]

    @classmethod
    async def _get_category_name(cls, category_id):
        if category_id not in cls.CATEGORIES:
            url = "{sr_api_url}/categories/{category_id}".format(sr_api_url=cfg.SR_API_URL, category_id=category_id)
            category = await cls.get_data(url)
            cls.CATEGORIES[category_id] = category['name']
        return cls.CATEGORIES[category_id]


class WorldRecord(SpeedrunData):
    RESOURCE_NAME = "world record"

    @classmethod
    async def parse(cls, elem):
        tasks = [
            cls._get_game_name(cls._get_game_id(elem)),
            cls._get_category_name(cls._get_category_id(elem))
        ]
        game_name, category_name = await asyncio.gather(*tasks)
        return {
            'game_name': str(game_name),
            'category_name': str(category_name),
            'time': utils.convert_time(elem['runs'][0]['run']['times']['realtime_t']),
            'url': elem['runs'][0]['run']['videos']['links'][0]['uri']
        }

    @staticmethod
    def _get_game_id(elem):
        return elem['runs'][0]['run']['game']

    @staticmethod
    def _get_category_id(elem):
        return elem['runs'][0]['run']['category']

    @staticmethod
    def get_url(game):
        return "{sr_api_url}/games/{game}/records?top=1".format(sr_api_url=cfg.SR_API_URL, game=game)


class PersonalBest(SpeedrunData):
    RESOURCE_NAME = "personal best"

    @classmethod
    async def parse(cls, elem):
        tasks = [
            cls._get_game_name(cls._get_game_id(elem)),
            cls._get_category_name(cls._get_category_id(elem))
        ]
        game_name, category_name = await asyncio.gather(*tasks)
        return {
            'place': utils.ordinal(elem['place']),
            'game_name': game_name,
            'category_name': category_name,
            'time': utils.convert_time(elem['run']['times']['realtime_t']),
            'url': elem['run']['videos']['links'][0]['uri']
        }

    @staticmethod
    def _get_game_id(elem):
        return elem['run']['game']

    @staticmethod
    def _get_category_id(elem):
        return elem['run']['category']

    @staticmethod
    def get_url(username, game):
        return "{sr_api_url}/users/{username}/personal-bests?game={game}"\
                .format(sr_api_url=cfg.SR_API_URL, username=username, game=game or "")


class Speedrun:

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def sr(self, ctx, username, game=None):
        url = PersonalBest.get_url(username, game)
        personal_bests = await PersonalBest.get_data(url)
        summary = collections.defaultdict(dict)
        summary_elems = await asyncio.gather(*[PersonalBest.parse(pb) for pb in personal_bests])
        for summary_elem in summary_elems:
            summary[summary_elem['game_name']][summary_elem['category_name']] = summary_elem
        embed = PersonalBest.get_embed(summary)
        await ctx.message.channel.send("Summary for {username}".format(username=username), embed=embed)

    @commands.command()
    async def wr(self, ctx, game):
        url = WorldRecord.get_url(game)
        records = await WorldRecord.get_data(url)
        summary = collections.defaultdict(dict)
        summary_elems = await asyncio.gather(*[WorldRecord.parse(record) for record in records if record['runs']])
        for summary_elem in summary_elems:
            summary[summary_elem['game_name']][summary_elem['category_name']] = summary_elem
        embed = WorldRecord.get_embed(summary)
        await ctx.message.channel.send("Worlds records for {game}".format(game=game), embed=embed)


def setup(bot):
    bot.add_cog(Speedrun(bot))

import asyncio
from argparse import ArgumentParser
from os.path import isfile
from pathlib import Path

import aiosqlite
from irctokens import build, Line
from ircrobots import Bot as BaseBot
from ircrobots import Server as BaseServer
from ircrobots import ConnectionParams

from .config import Config, load as config_load


class Server(BaseServer):
    def __init__(
        self, bot: BaseBot, name: str, config: Config, database: aiosqlite.Connection
    ):
        super().__init__(bot, name)
        self._config = config
        self._database = database

    async def line_read(self, line: Line):
        print(f"{self.name} < {line.format()}")

        if (
            line.command == "JOIN"
            and self.casefold(line.params[0]) in self._config.channels
            and not self.casefold_equals(line.hostmask.nickname, self.nickname)
        ):
            # a user has joined one of our watched channels

            channel = self.casefold(line.params[0])

            if not line.params[1] == "*":
                # go by account name
                key = self.casefold(line.params[1])
            else:
                # go by user@host
                username = self.casefold(line.hostmask.username)
                key = f"{username}@{line.hostmask.hostname}"

            db_cursor = await self._database.execute(
                "SELECT key FROM seen WHERE channel = ? AND key = ?", [channel, key]
            )
            user_new = (await db_cursor.fetchone()) is None
            if user_new:
                await self._database.execute(
                    "INSERT INTO seen (channel, key) VALUES (?, ?)", [channel, key]
                )
                await self._database.commit()

                greet = self._config.channels[channel]
                greet = greet.format(nickname=line.hostmask.nickname, channel=channel)
                await self.send(build("PRIVMSG", [channel, greet]))

        if (
            line.command == "ACCOUNT"
            and not line.params[0] == "*"
            and not self.casefold_equals(line.hostmask.nickname, self.nickname)
        ):
            # a user, in one or more of our channels, has logged in to an account.
            # mark the account as seen for all our watched channel they're already
            # in, given they'll have already been greeted

            account = self.casefold(line.params[0])
            user = self.users[self.casefold(line.hostmask.nickname)]
            for channel in set(self._config.channels.keys()) & user.channels:
                db_cursor = await self._database.execute(
                    "SELECT key FROM seen WHERE channel = ? AND key = ?",
                    [channel, account],
                )
                user_new = (await db_cursor.fetchone()) is None
                if not user_new:
                    continue

                await self._database.execute(
                    "INSERT INTO seen (channel, key) VALUES (?, ?)", [channel, account]
                )
                await self._database.commit()

    async def line_send(self, line: Line):
        print(f"{self.name} > {line.format()}")


class Bot(BaseBot):
    def __init__(self, config: Config, database: aiosqlite.Connection):
        super().__init__()
        self._config = config
        self._database = database

    def create_server(self, name: str):
        return Server(self, name, self._config, self._database)


async def main():
    parser = ArgumentParser(description="a bot to welcome new users to IRC channels")
    parser.add_argument("config", help="path to this bot's config file", type=Path)
    args = parser.parse_args()

    config = config_load(args.config)

    database_new = not isfile(config.database)
    database = await aiosqlite.connect(config.database)
    if database_new:
        await database.execute(
            "CREATE TABLE seen (channel TEXT, key TEXT, PRIMARY KEY (channel, key))"
        )
        await database.commit()

    bot = Bot(config, database)

    params = ConnectionParams.from_hoststring(config.nickname, config.server)
    params.username = config.username
    params.realname = config.realname
    params.autojoin = list(config.channels.keys())

    if config.sasl is not None:
        sasl_username, sasl_password = config.sasl
        params.sasl = SASLUserPass(sasl_username, sasl_password)

    await bot.add_server("irc", params)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())

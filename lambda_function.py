import os
import json

import telegram

# Checks for environment variables
print("Loading function")
print(f"Bot name: {os.environ['BOT_NAME']}")
print(f"Bot token: {os.environ['BOT_TOKEN']}")
print(f"DynamoDB table name: {os.environ['TABLE_NAME']}")
print(f"is_open index name: {os.environ['IS_OPEN_INDEX_NAME']}")

import trade
from errors import InputError, NotRelevantError


class Chat:
    def __init__(self, chat_id, username):
        self.bot = telegram.Bot(token=os.environ["BOT_TOKEN"])
        self.chat_id = chat_id
        self.username = username

    def respond(self, message=None):
        if message is not None:
            self.bot.send_message(
                chat_id=self.chat_id, text=f"<code>{message}</code>", parse_mode="html"
            )


def lambda_handler(event, context):
    event_body = json.loads(event["body"])

    # Edited messages do not have "message" in event_body
    if "message" not in event_body:
        return {"statusCode": 200, "body": json.dumps({})}

    chat_id = event_body["message"]["chat"]["id"]
    username = event_body["message"]["from"]["username"]
    chat = Chat(chat_id, username)

    try:
        main(event_body, chat)
    except InputError as e:
        chat.respond(str(e))
    except Exception as e:
        chat.respond("Internal error")
        print(f"Unexpected error: {e}")
    finally:
        return {"statusCode": 200, "body": json.dumps({})}


def main(event_body, chat):
    # Messages may not contain text
    if "text" not in event_body["message"]:
        return

    text = event_body["message"]["text"].split(" ")

    # Filter out non-slash-commands
    if not text[0].startswith("/"):
        return

    action_list = text[0][1:].split("@")

    # References to other bots
    if len(action_list) > 1 and action_list[1] != os.environ["BOT_NAME"]:
        return

    action = action_list[0]

    # /long(short) SYMBOL AMOUNT
    if action in ["long", "short"]:
        if len(text) < 3:
            return chat.respond("Include symbol and amount in your command")

        symbol = text[1]
        amount = float(text[2])
        price, new_buying_power = trade.set_trade(
            user=chat.username, action=action, symbol=symbol, amount=amount
        )

        return chat.respond(
            f"{amount} {symbol} bought at {price}. Current buying power: {'{:.2f}'.format(new_buying_power)}"
        )

    # /close TRADE_ID
    if action == "close":
        if len(text) < 2:
            return chat.respond("Include trade ID in your command")

        trade_id = text[1]
        profit, current_price, symbol = trade.close_trade(chat.username, trade_id)
        return chat.respond(
            f"{symbol} successfully closed at {current_price} for a profit of: {profit}"
        )

    # /list
    if action == "list":
        return chat.respond(trade.list_open_trades(chat.username))

    # /stats (USERNAME)
    if action == "stats":
        user = chat.username
        if len(text) == 2:
            user = text[1].split("@")[-1]
        return chat.respond(trade.show_stats(user))

    # /check SYMBOL
    if action == "check":
        if len(text) < 2:
            return chat.respond("Include symbol in your command")

        symbol = text[1].upper()
        return chat.respond(f"{symbol}: {trade.get_price(symbol)}")

    return chat.respond("Invalid command")

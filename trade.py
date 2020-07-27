import json
import os
import time
import uuid

from botocore.exceptions import ClientError
from dynamodb_json import json_util as djson
from prettytable import PrettyTable, NONE
import boto3
import requests

from errors import InputError

db_client = boto3.client("dynamodb")
table_name = os.environ["TABLE_NAME"]
is_open_index_name = os.environ["IS_OPEN_INDEX_NAME"]


def djsonify(d):
    return json.loads(djson.dumps(d))


def set_trade(user, action, symbol, amount):
    symbol_price = get_price(symbol)
    buying_power_used = symbol_price * amount
    buying_power = check_user_buying_power(user, buying_power_used)
    new_buying_power = buying_power - buying_power_used

    db_client.update_item(
        TableName=table_name,
        Key=djsonify({"pk": user, "sk": "user"}),
        UpdateExpression="SET buying_power=:value1",
        ExpressionAttributeValues=djsonify(
            {":value1": float("{:.2f}".format(new_buying_power))}
        ),
    )

    trade_time = int(time.time())

    db_client.put_item(
        TableName=table_name,
        Item=json.loads(
            djson.dumps(
                {
                    "pk": str(uuid.uuid4())[:8],
                    "sk": user,
                    "action": action,
                    "symbol": symbol,
                    "amount": amount,
                    "open_price": symbol_price,
                    "is_open": trade_time,
                    "created_at": trade_time,
                }
            )
        ),
    )

    return symbol_price, new_buying_power


def close_trade(user, trade_id):
    trade_data = djson.loads(
        db_client.get_item(
            TableName=table_name, Key=djsonify({"pk": trade_id, "sk": user}),
        )
    )

    if trade_data.get("Item") is None:
        raise InputError("Invalid trade ID")

    trade_symbol = trade_data["Item"]["symbol"]
    trade_amount = trade_data["Item"]["amount"]
    open_price = trade_data["Item"]["open_price"]
    current_price = get_price(trade_symbol)
    action_multipler = 1 if trade_data["Item"]["action"] == "long" else -1
    commission = current_price * trade_amount * 0.001
    profit = float(
        "{:.2f}".format(
            (current_price - open_price) * trade_amount * action_multipler - commission
        )
    )
    bp_change = float("{:.2f}".format(current_price * trade_amount - commission))

    try:
        db_client.update_item(
            TableName=table_name,
            Key=djsonify({"pk": trade_id, "sk": user}),
            UpdateExpression="REMOVE is_open SET closed_at=:value1, close_price=:value2, profit=:value3",
            ConditionExpression="attribute_exists(is_open)",
            ExpressionAttributeValues=djsonify(
                {
                    ":value1": int(time.time()),
                    ":value2": current_price,
                    ":value3": profit,
                }
            ),
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise InputError("Trade already closed")
        else:
            raise

    if profit <= 0:
        update_string = "losses"
    else:
        update_string = "wins"

    db_client.update_item(
        TableName=table_name,
        Key=djsonify({"pk": user, "sk": "user"}),
        UpdateExpression=f"SET buying_power=buying_power+:value1, {update_string}={update_string}+:value2, realised_pnl=realised_pnl+:value3",
        ExpressionAttributeValues=djsonify(
            {":value1": bp_change, ":value2": 1, ":value3": profit,}
        ),
    )

    return profit, current_price, trade_symbol


def get_price(symbol):
    response = requests.get(
        "https://fapi.binance.com/fapi/v1/ticker/price", params={"symbol": symbol}
    )

    if response.status_code == 200:
        return float(response.json()["price"])

    raise InputError("Invalid symbol")


def check_user_buying_power(user, buying_power_used):
    user_data = djson.loads(
        db_client.get_item(
            TableName=table_name, Key=djsonify({"pk": user, "sk": "user"}),
        )
    )

    if user_data.get("Item") is None:
        buying_power = create_user(user)
    else:
        buying_power = user_data["Item"]["buying_power"]

    if buying_power < buying_power_used:
        raise InputError("Not enough buying power")

    return buying_power


def create_user(user):
    default_amount = 100000

    db_client.put_item(
        TableName=table_name,
        Item=json.loads(
            djson.dumps(
                {
                    "pk": user,
                    "sk": "user",
                    "buying_power": default_amount,
                    "wins": 0,
                    "losses": 0,
                    "realised_pnl": 0,
                }
            )
        ),
    )

    return default_amount


def list_open_trades(user):
    output = PrettyTable(border=False, vrules=NONE)
    output.align = "r"
    output.field_names = ["id", "act", "sym", "amt", "opn", "cur"]

    results = djson.loads(
        db_client.query(
            TableName=table_name,
            IndexName=is_open_index_name,
            KeyConditionExpression="sk=:value1",
            ExpressionAttributeValues=djsonify({":value1": user}),
        )
    )["Items"]

    if results == []:
        return "You have no open trades at the moment"

    price_dict = {}

    for item in results:
        trade_id = item["pk"]
        action = item["action"].upper()
        symbol = item["symbol"].upper()
        amount = item["amount"]
        price = item["open_price"]
        if symbol not in price_dict:
            price_dict[symbol] = get_price(symbol)
        current_price = price_dict[symbol]
        output.add_row([trade_id, action, symbol, amount, price, current_price])

    return str(output)


def show_stats(user):
    output = PrettyTable(border=False, vrules=NONE)
    output.align = "r"
    output.field_names = ["user", "w/l", "pnl", "bp"]

    user_data = djson.loads(
        db_client.get_item(
            TableName=table_name, Key=djsonify({"pk": user, "sk": "user"}),
        )
    )

    if user_data.get("Item") is None:
        create_user(user)
        return f"No user found! New user created for {user}"

    item = user_data["Item"]
    user = item["pk"]
    wl = f"{item['wins']}/{item['losses']}"
    pnl = item["realised_pnl"]
    bp = item["buying_power"]
    output.add_row([user, wl, pnl, bp])

    return str(output)

# Crypto Paper Trading Bot

This is a basic paper trading bot using market prices from Binance Futures.

## Prerequisites

### Telegram bot

1. Create a Telegram bot using BotFather
1. Note down the token

### AWS Account

1. Create a DynamoDB table with the following params:
   - Partition key: "pk"
   - Sort key: "sk"
1. Create a index for the table with the following params:
   - Partition key: "sk"
   - Sort key: "is_open"
1. Create an API on API Gateway that links to a Lambda
1. Add the following environment variables to the Lambda
   - BOT_NAME: The bot's Telegram username
   - BOT_TOKEN: The bot's token
   - TABLE_NAME: Name of the DynamoDB table
   - IS_OPEN_INDEX_NAME: Name of the index created in step 2.
1. Publish the API
1. Use the [`setWebhook`](https://core.telegram.org/bots/api#setwebhook) API to set the webhook to the URL under `Stages > default > Invoke URL`

## Deployment

1. Ensure you have a virtual environment set up (preferable under `.venv`)
1. Install the requirements using `pip install -r requirements.txt`. Install `awscli` if you do not have it.
1. Run `FUNCTION_NAME=<name of the lambda> make`

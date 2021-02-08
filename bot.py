import requests
import os
import json
import boto3

_bot_token = os.getenv('TELEGRAM_TOKEN')


def handle_update(update, context):
    message = update['message']
    chat = message['chat']

    # This just echo-replies with the message text.
    return {
        'method': 'sendMessage',
        'chat_id': chat['id'],
        'reply_to_message_id': message['message_id'],
        'text': message['text']
    }


def _invoke_lambda(lambda_name: str, args: dict):
    lamb = boto3.client('lambda')
    return lamb.invoke(
        FunctionName=lambda_name,
        InvocationType='Event',
        Payload=json.dumps(args)
    )


def _request_url(method: str):
    return f"https://api.telegram.org/bot{_bot_token}/{method}"

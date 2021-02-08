resource "telegram_bot_webhook" "bot" {
  url = "https://${cloudflare_record.bot.name}${aws_api_gateway_resource.token.path}"
  # See https://core.telegram.org/bots/api#update
  allowed_updates = [
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
    "inline_query",
    "chosen_inline_result",
    "callback_query",
    "shipping_query",
    "pre_checkout_query",
    "poll",
    "poll_answer"
  ]
}

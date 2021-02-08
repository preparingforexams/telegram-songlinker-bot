resource "telegram_bot_webhook" "bot" {
  url = "https://${cloudflare_record.bot.name}${aws_api_gateway_resource.token.path}"
  # See https://core.telegram.org/bots/api#update
  allowed_updates = [
    "message",
    "inline_query"
  ]
}

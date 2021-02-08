# telegram-bot-template

Template repo for python telegram bots hosted in AWS with a Cloudflare domain.

## Implementation

Just add your code in `bot.py`.

## Deployment

### Configuration

Choose a workspace name in `terraform/providers.tf` (marked as TODO).

Supply in a `.tfvars`-file in the terraform dir:

- `cloudflare_token`
- `telegram_token`
- `bot_name`

### Packaging

Package the requirements:

```sh
pip3 install -r requirements.txt -t python && zip -r layer.zip python
```

Package the code:

```sh
zip code.zip *.py
```

### Yeet service into existence

Have Terraform, the [Telegram Provider](https://github.com/yi-jiayu/terraform-provider-telegram)
and the AWS CLI installed and configured. Then, in the terraform dir:

```sh
terraform init
```

Change the terraform cloud workspace to local execution. Then:

```sh
terraform apply
```

And you're done.

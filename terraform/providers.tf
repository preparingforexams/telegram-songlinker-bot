terraform {
  backend "remote" {
    hostname = "app.terraform.io"

    workspaces {
      # TODO: name = "workspacename"
    }
  }

  required_providers {
    aws = {
      source = "hashicorp/aws"
    }

    cloudflare = {
      source = "terraform-providers/cloudflare"
    }

    telegram = {
      source  = "inhouse.local/local/telegram"
      version = "0.2.0"
    }
  }

}

variable "cloudflare_token" {}

provider "cloudflare" {
  api_token = var.cloudflare_token
}

variable "aws_region" {
  default = "eu-central-1"
}

provider "aws" {
  profile = "default"
  region  = var.aws_region
}

provider "telegram" {
  bot_token = var.telegram_token
}

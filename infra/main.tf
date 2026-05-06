terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-northeast-1"
}

resource "aws_s3_bucket" "my_portfolio_bucket" {
  bucket = "melyuh-portfolio"
}

# ---------------------------------------------
# 1. OAC (Origin Access Control) の作成
# CloudFrontからS3への安全なアクセスを提供する最新の仕組みです
# ---------------------------------------------
resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "melyuh-portfolio-oac"
  description                       = "OAC for portfolio site"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ---------------------------------------------
# 2. CloudFront ディストリビューションの作成
# 世界中にサイトを高速配信するCDN本体です
# ---------------------------------------------
resource "aws_cloudfront_distribution" "cdn" {
  origin {
    domain_name              = aws_s3_bucket.my_portfolio_bucket.bucket_regional_domain_name
    origin_id                = aws_s3_bucket.my_portfolio_bucket.id
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html" # URLの末尾がない場合に表示するファイル

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = aws_s3_bucket.my_portfolio_bucket.id

    # AWSが用意しているキャッシュ最適化の標準ポリシーを使用
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    viewer_protocol_policy = "redirect-to-https" # HTTPアクセスをHTTPSに強制リダイレクト
  }

  restrictions {
    geo_restriction {
      restriction_type = "none" # 全世界からアクセス可能
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true # CloudFrontの標準SSL証明書を使用
  }
}

# ---------------------------------------------
# 3. S3バケットポリシーの作成
# 「上で作ったCloudFrontからのアクセスだけを許可する」というルールをS3に適用します
# ---------------------------------------------
resource "aws_s3_bucket_policy" "bucket_policy" {
  bucket = aws_s3_bucket.my_portfolio_bucket.id
  policy = data.aws_iam_policy_document.s3_policy.json
}

data "aws_iam_policy_document" "s3_policy" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.my_portfolio_bucket.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.cdn.arn]
    }
  }
}

# ---------------------------------------------
# 4. 出力設定 (Outputs)
# デプロイ完了時に、生成されたサイトのURLをターミナルに表示させます
# ---------------------------------------------
output "portfolio_url" {
  value       = "https://${aws_cloudfront_distribution.cdn.domain_name}"
  description = "ポートフォリオサイトの公開URL"
}
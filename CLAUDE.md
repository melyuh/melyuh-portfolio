# CLAUDE.md

## Memory

At each natural break in work (task completed, topic changes, before rebuilds), write important context (decisions made, work done, user preferences) to the memory system at `/home/vscode/.claude/projects/-workspaces-portfolio/memory/`. This ensures continuity across devcontainer rebuilds and new sessions.

## Project Overview

SREポートフォリオサイト。静的HTMLをS3+CloudFrontで配信するAWSインフラをTerraformで管理している。

## Key Constraints

- `infra/setup-backend/` は初回のみ実行。一度セットアップしたら原則触らない
- `*.tfvars` と `*.tfstate` は `.gitignore` されている
- CloudFrontはHTTPSのみ許可。S3はCloudFront OAC経由のアクセスのみ許可

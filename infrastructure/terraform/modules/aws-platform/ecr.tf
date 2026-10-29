# One ECR repository per EnvForge service image — the cloud equivalent of
# the locally-built `envforge-api`/`envforge-worker`/`envforge-frontend`
# images `make build-sample-backend` (and friends) produce for `kind`.
# Immutable tags only: CI pushes `${service}:${git_sha}`, matching the
# immutable-SHA-tag rule already enforced for the local images (see
# .github/workflows/backend.yml's container-scan job).

resource "aws_ecr_repository" "this" {
  for_each = toset(var.ecr_repository_names)

  name                 = each.value
  image_tag_mutability = var.ecr_image_tag_mutability

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after 7 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 7
      }
      action = { type = "expire" }
    }]
  })
}

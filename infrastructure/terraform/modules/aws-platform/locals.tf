locals {
  name = "${var.project_name}-${var.environment_name}"

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment_name
      ManagedBy   = "terraform"
    },
    var.tags,
  )

  az_count = min(var.availability_zone_count, length(data.aws_availability_zones.available.names))
  azs      = slice(data.aws_availability_zones.available.names, 0, local.az_count)
}

data "aws_availability_zones" "available" {
  state = "available"
}

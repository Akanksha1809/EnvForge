module "platform" {
  source = "../../modules/aws-platform"

  aws_region       = var.aws_region
  environment_name = var.environment_name
}

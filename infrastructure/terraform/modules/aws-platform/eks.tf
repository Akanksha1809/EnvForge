# EKS cluster + one managed node group. Deliberately hand-written (no
# third-party registry module) so every resource here is something a
# reviewer can read end-to-end without fetching and auditing someone
# else's module first.

resource "aws_iam_role" "cluster" {
  name = "${local.name}-eks-cluster"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_security_group" "cluster" {
  name_prefix = "${local.name}-eks-cluster-"
  vpc_id      = aws_vpc.this.id
  tags        = merge(local.common_tags, { Name = "${local.name}-eks-cluster-sg" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_eks_cluster" "this" {
  name     = local.name
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = concat(aws_subnet.public[*].id, aws_subnet.private[*].id)
    security_group_ids      = [aws_security_group.cluster.id]
    endpoint_public_access  = true
    endpoint_private_access = true
  }

  access_config {
    authentication_mode = "API_AND_CONFIG_MAP"
  }

  tags = local.common_tags

  depends_on = [aws_iam_role_policy_attachment.cluster_policy]
}

# IRSA (IAM Roles for Service Accounts): lets in-cluster workloads (e.g.
# the AWS Load Balancer Controller, below) assume a scoped IAM role via
# their Kubernetes service account token, instead of the node's own
# instance role — the standard least-privilege pattern for EKS.
resource "aws_iam_openid_connect_provider" "this" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["9e99a48a9960b14926bb7f3b02e22da2b0ab7280"]

  tags = local.common_tags
}

resource "aws_iam_role" "node_group" {
  name = "${local.name}-eks-node-group"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "node_worker" {
  role       = aws_iam_role.node_group.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "node_cni" {
  role       = aws_iam_role.node_group.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "node_ecr_readonly" {
  role       = aws_iam_role.node_group.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${local.name}-default"
  node_role_arn   = aws_iam_role.node_group.arn
  subnet_ids      = aws_subnet.private[*].id
  instance_types  = var.node_instance_types

  scaling_config {
    min_size     = var.node_group_min_size
    max_size     = var.node_group_max_size
    desired_size = var.node_group_desired_size
  }

  update_config {
    max_unavailable = 1
  }

  tags = local.common_tags

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr_readonly,
  ]

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}

# IRSA role for the AWS Load Balancer Controller — this is EnvForge's
# cloud equivalent of the local path's ingress-nginx: it watches Kubernetes
# Ingress objects and provisions real ALBs in response. The controller
# itself is installed via its Helm chart (not Terraform, same division of
# labor as ingress-nginx locally); this role is the IAM half it needs.
data "aws_iam_policy_document" "lb_controller_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.this.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_iam_openid_connect_provider.this.url, "https://", "")}:sub"
      values   = ["system:serviceaccount:kube-system:aws-load-balancer-controller"]
    }
  }
}

resource "aws_iam_role" "lb_controller" {
  name               = "${local.name}-lb-controller"
  assume_role_policy = data.aws_iam_policy_document.lb_controller_assume.json
  tags               = local.common_tags
}

# The AWS Load Balancer Controller's IAM policy is a large third-party
# published document (~900 lines) — referenced here by its documented
# source rather than hand-copied, same as any dependency's license file.
resource "aws_iam_role_policy" "lb_controller" {
  name   = "${local.name}-lb-controller-policy"
  role   = aws_iam_role.lb_controller.id
  policy = file("${path.module}/policies/aws-load-balancer-controller.json")
}

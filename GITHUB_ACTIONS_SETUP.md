# GitHub Actions CI/CD Setup Guide

## Overview
This guide helps you set up GitHub Actions to automatically build and deploy your chatbot application to AWS ECR.

## Prerequisites
1. **GitHub Repository** - Your code must be in a GitHub repository
2. **AWS Account** - With ECR repository and optional ECS service
3. **IAM Role** - For GitHub Actions to assume and push to ECR

## Step 1: Create AWS IAM Role for GitHub

### Option A: Using AWS CloudFormation (Recommended)

```bash
# Create trust policy for GitHub OIDC
aws iam create-open-id-connect-provider \
    --url "https://token.actions.githubusercontent.com" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"
```

### Option B: Manual IAM Setup

1. Go to **IAM Console → Roles → Create Role**
2. Choose **Web identity**
3. Select **token.actions.githubusercontent.com** as provider
4. Add audience: `sts.amazonaws.com`
5. Attach policy: `AmazonEC2ContainerRegistryPowerUser`

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_ORG/YOUR_REPO:*"
        }
      }
    }
  ]
}
```

## Step 2: Add GitHub Secrets

Go to **GitHub Repository → Settings → Secrets and variables → Actions**

Add these secrets:

### Required Secrets
- `AWS_ROLE_ARN` - ARN of the IAM role created above
  - Format: `arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME`

### Optional Secrets (for deployment)
- `ECS_CLUSTER` - Your ECS cluster name
- `ECS_SERVICE` - Your ECS service name
- `ECS_TASK_DEFINITION` - Your task definition name

## Step 3: Configure Workflows

Three workflow files are included:

### 1. **build-and-push.yml** (Automatic on Push)
- **Trigger:** Pushes to `main` or `develop` branches
- **Action:** 
  - Runs tests and linting
  - Builds Docker image
  - Pushes to ECR with tags: `latest`, `SHA`, `branch-name`
- **No manual action required** - Runs automatically

### 2. **deploy-to-ecs.yml** (Automatic Deployment)
- **Trigger:** After successful ECR push
- **Action:** Updates ECS service with new image
- **Requires:** ECS setup

### 3. **manual-ecr-push.yml** (Manual Trigger)
- **Trigger:** Manual workflow dispatch
- **Action:** Push to staging or production environment
- **Access:** Repository → Actions → Manual ECR Push

## Step 4: Update Environment Variables

Edit `.github/workflows/build-and-push.yml`:

```yaml
env:
  AWS_REGION: ap-south-1              # ✓ Already set
  ECR_REPOSITORY: modicare-rag        # ✓ Already set
  IMAGE_TAG: latest                   # ✓ Already set
```

Edit `.github/workflows/deploy-to-ecs.yml`:

```yaml
env:
  AWS_REGION: ap-south-1              # Update if needed
  ECS_CLUSTER: your-cluster-name      # Update this
  ECS_SERVICE: your-service-name      # Update this
  ECS_TASK_DEFINITION: your-task-def  # Update this
```

## Step 5: Update Your Dockerfile (if needed)

Ensure your `Dockerfile` exists and is valid:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "app.py"]
```

## Usage

### Automatic Deployment (Recommended)
1. Make changes to your code
2. Commit and push to `main` branch:
   ```bash
   git add .
   git commit -m "Your message"
   git push origin main
   ```
3. GitHub Actions automatically:
   - Runs tests
   - Builds Docker image
   - Pushes to ECR

### Manual Deployment
1. Go to **Repository → Actions → Manual ECR Push**
2. Click **Run workflow**
3. Select environment (staging/production)
4. Click **Run workflow**

## Monitoring

### View Workflow Logs
1. Go to **Repository → Actions**
2. Click on the workflow run
3. Click on job to see detailed logs

### Check ECR Images
```bash
aws ecr describe-images \
    --repository-name modicare-rag \
    --region ap-south-1
```

### Verify ECS Deployment
```bash
aws ecs describe-services \
    --cluster modicare-rag-cluster \
    --services modicare-rag-service \
    --region ap-south-1
```

## Troubleshooting

### Authentication Failed
- Verify AWS_ROLE_ARN secret is correct
- Check trust policy allows your repository
- Ensure IAM role has `AmazonEC2ContainerRegistryPowerUser` permission

### Docker Build Failed
- Check Dockerfile syntax
- Verify requirements.txt is valid
- Ensure all necessary files are committed

### ECS Deployment Failed
- Verify ECS cluster and service names
- Check task definition exists
- Ensure container name matches in task definition

## Advanced: Branch-Specific Deployments

To deploy only specific branches:

Edit `.github/workflows/build-and-push.yml`:

```yaml
on:
  push:
    branches:
      - main          # Production
      - develop       # Staging
      - hotfix/*      # Hotfixes
```

## Next Steps

1. ✅ Push code to GitHub
2. ✅ GitHub Actions will automatically build and push to ECR
3. ✅ (Optional) Set up ECS deployment
4. ✅ Monitor deployments in Actions tab

## Support Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [AWS OIDC Provider Setup](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [Amazon ECR Push](https://github.com/aws-actions/amazon-ecr-login)
- [ECS Deploy Task Definition](https://github.com/aws-actions/ecs-deploy-task-definition)

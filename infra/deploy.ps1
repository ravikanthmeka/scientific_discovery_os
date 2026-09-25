param (
    [string]$EnvFile = "..\backend\.env"
)

$ErrorActionPreference = "Stop"

function Run-Command {
    param([scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Command failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

Write-Host "Loading AWS credentials from $EnvFile..."
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match "^(AWS_.*?)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
} else {
    Write-Host "No .env file found at $EnvFile. Make sure AWS credentials are set!" -ForegroundColor Yellow
}

Write-Host "Ensuring Terraform State Bucket exists..."
$BucketName = "sdo-terraform-state-bucket"
try {
    $null = aws s3api head-bucket --bucket $BucketName 2>&1
    Write-Host "S3 Bucket $BucketName already exists."
} catch {
    Write-Host "Creating S3 Bucket $BucketName for Terraform state..."
    Run-Command { aws s3api create-bucket --bucket $BucketName --region us-east-1 }
    Run-Command { aws s3api put-bucket-versioning --bucket $BucketName --versioning-configuration Status=Enabled }
}

Write-Host "Ensuring DynamoDB State Lock Table exists..."
$TableName = "sdo-terraform-state-lock"
try {
    $null = aws dynamodb describe-table --table-name $TableName 2>&1
    Write-Host "DynamoDB table $TableName already exists."
} catch {
    Write-Host "Creating DynamoDB table $TableName for Terraform state locking..."
    Run-Command { 
        aws dynamodb create-table --table-name $TableName `
            --attribute-definitions AttributeName=LockID,AttributeType=S `
            --key-schema AttributeName=LockID,KeyType=HASH `
            --billing-mode PAY_PER_REQUEST `
            --region us-east-1 | Out-Null
    }
    Write-Host "Waiting for table to become active..."
    Run-Command { aws dynamodb wait table-exists --table-name $TableName }
}

if (-not (Test-Path "prod.tfvars")) {
    Write-Host "prod.tfvars not found! Please create one based on the template." -ForegroundColor Red
    exit 1
}

Write-Host "Initializing Terraform..."
Run-Command { terraform init }

Write-Host "Applying Terraform configuration..."
Run-Command { terraform apply -var-file="prod.tfvars" -auto-approve }

$ECR_URL = terraform output -raw ecr_repository_url
$ALB_URL = terraform output -raw alb_dns_name
$FRONTEND_BUCKET = "sdo-prod-frontend-app"

Write-Host "Logging into AWS ECR..."
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URL
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Building Backend Docker image..."
cd ..\backend
Run-Command { docker build -t sdo-backend . }
Run-Command { docker tag sdo-backend:latest "$($ECR_URL):latest" }

Write-Host "Pushing Docker image to ECR..."
Run-Command { docker push "$($ECR_URL):latest" }

Write-Host "Forcing ECS deployment to pull new image..."
Run-Command { aws ecs update-service --cluster sdo-prod-cluster --service sdo-prod-backend-service --force-new-deployment --region us-east-1 | Out-Null }

Write-Host "Building Frontend..."
cd ..\frontend
$FrontendEnvPath = ".env"
$DomainName = (Get-Content ..\infra\prod.tfvars | Select-String -Pattern 'domain_name\s*=\s*"([^"]+)"').Matches.Groups[1].Value
if ($DomainName) {
    Set-Content -Path $FrontendEnvPath -Value "VITE_BACKEND_URL=https://api.$DomainName"
} else {
    Set-Content -Path $FrontendEnvPath -Value "VITE_BACKEND_URL=http://$ALB_URL"
}
Run-Command { npm install }
Run-Command { npm run build }

Write-Host "Uploading Frontend to S3..."
Run-Command { aws s3 sync dist/ s3://$FRONTEND_BUCKET/ --delete }

Write-Host "Deployment Complete!" -ForegroundColor Green


Write-Host "Invalidating CloudFront cache..."
Run-Command { aws cloudfront create-invalidation --distribution-id EI0J14YV1UXCH --paths "/*" }

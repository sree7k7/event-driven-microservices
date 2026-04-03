## AWS event driven microservices.

In progress .......

Microservices decoupled architecture with distinct paths, container and serverless pathways.

### Design

```mermaid

graph TD
    %% Define User
    User((Web & Mobile Clients))

    %% Phase 1 & 4: Edge & Routing
    subgraph "Edge Layer (Phases 1 & 4)"
        Route53[Amazon Route 53 DNS]
        CloudFront[Amazon CloudFront CDN]
        WAF{AWS WAF}
    end

    %% API & Routing Layer
    subgraph "Traffic Routing Layer (Phase 4)"
        APIGW[API Gateway - OrderProcessingAPI]
        ALB[Application Load Balancer]
    end

    %% Phase 1: VPC Foundation
    subgraph "Amazon VPC (Phase 1)"
        NAT[NAT Gateway]
        
        subgraph "Private Subnets (The Vault)"
            ECS[Amazon ECS Fargate Containers]
            RDS[(Amazon RDS PostgreSQL)]
            ElastiCache[(ElastiCache Valkey)]
        end
    end

    %% Phase 3: Serverless Compute
    subgraph "Serverless Compute (Phase 3)"
        Worker1[Lambda: ProcessOrderWorker]
        Worker2[Lambda: ReceiptGenerator]
    end

    %% Phase 2: Data & Storage
    subgraph "Data & Storage (Phase 2)"
        DynamoDB[(Amazon DynamoDB)]
        S3[Amazon S3 Storage]
    end

    %% Phase 5: Integration
    subgraph "Integration & Decoupling (Phase 5)"
        SNS((SNS: OrderCreatedTopic))
        SQS[[SQS: ReceiptQueue]]
    end

    %% Phase 6: Observability & DevOps
    subgraph "Monitoring & DevOps (Phase 6)"
        CW[Amazon CloudWatch]
        XRay[AWS X-Ray]
        ECR[Amazon ECR]
        CICD[CodePipeline & CodeBuild]
    end

    %% ---- THE CONNECTIONS & TRAFFIC FLOW ----

    %% User to Edge
    User --> Route53
    Route53 --> CloudFront
    CloudFront --- WAF

    %% Edge to Routing & Storage
    CloudFront -->|Static Files| S3
    CloudFront -->|Dynamic Web Traffic| ALB
    CloudFront -->|API Calls| APIGW

    %% Routing to Compute
    ALB -->|Port 8080| ECS
    APIGW -->|POST /orders| Worker1

    %% Compute to State
    ECS -->|SQL queries| RDS
    ECS -->|Cache hits| ElastiCache
    Worker1 -->|NoSQL writes| DynamoDB
    Worker1 -.->|ENI Connection| RDS

    %% The Fan-Out Decoupling Flow
    ECS -->|Broadcasts Event| SNS
    Worker1 -->|Broadcasts Event| SNS
    SNS -->|Fan-out| SQS
    SQS -->|Triggers| Worker2

    %% DevOps & Monitoring (Dotted lines for background processes)
    CICD -.->|Pushes Docker Image| ECR
    ECR -.->|Pulls Image| ECS
    Worker1 -.->|Logs & Traces| CW
    Worker2 -.->|Logs & Traces| CW
    ECS -.->|Logs| CW
    Worker1 -.-> XRay
    Worker2 -.-> XRay
    
    %% Placeholder for custom steps
    
    CICD -.-> CustomSteps
```


The Front Door: The user hits Route 53 and CloudFront. The WAF acts as a shield (--- line) protecting the CDN.

The Split: CloudFront is smart. It grabs images from S3, sends web app traffic to the ALB, and sends data requests to the API Gateway.

The Work: The API Gateway hits your ProcessOrderWorker Lambda. The Lambda saves state to DynamoDB.

The Nervous System: The Lambda shouts to the SNS Topic, which drops the message into the SQS Queue, which wakes up the ReceiptGenerator Lambda safely in the background.

The Security Cameras: Those dotted lines (-.->) at the bottom represent all your resources quietly sending their health data to CloudWatch and X-Ray without slowing down the user experience.
## docker

```
1. Authenticate Docker with AWS
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 230150030147.dkr.ecr.us-east-1.amazonaws.com

2. Build the Docker Image Locally
docker build -t coffeeshop-app .

3. Tag the Image for AWS
docker tag coffeeshop-app:latest 230150030147.dkr.ecr.us-east-1.amazonaws.com/coffeeshop-app:latest

4. Push the Image to ECR
docker push 230150030147.dkr.ecr.us-east-1.amazonaws.com/coffeeshop-app:latest
```

## X-Ray, 

```
# 1. Create a new private repository for the X-Ray daemon
aws ecr create-repository --repository-name xray-daemon --region us-east-1

# 2. Log in (just in case your session expired)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 230150030147.dkr.ecr.us-east-1.amazonaws.com

# 3. Pull the public X-Ray daemon image to your laptop
docker pull amazon/aws-xray-daemon:latest

# 4. Re-tag it for your private AWS registry
docker tag amazon/aws-xray-daemon:latest 230150030147.dkr.ecr.us-east-1.amazonaws.com/xray-daemon:latest

# 5. Push the image securely into your private ECR vault
docker push 230150030147.dkr.ecr.us-east-1.amazonaws.com/xray-daemon:latest
```

## Connect to Container

### Drop into an interactive shell

```
aws ecs list-tasks --cluster CoffeeShopEcsCluster

aws ecs execute-command \
    --cluster CoffeeShopEcsCluster \
    --task <YOUR_TASK_ID> \
    --container AppContainer \
    --interactive \
    --command "/bin/sh"
```

 eg: install: ```apt-get update && apt-get install -y curl```,  ```curl -I https://xray.us-east-1.amazonaws.com```

```
# 1. Test the FastAPI health endpoint (This automatically generates an X-Ray trace!)
curl -s http://localhost:8080/health && echo -e "\n"

# 2. Test the Database Configuration endpoint (Proves Secrets Manager is working!)
curl -s http://localhost:8080/config-check && echo -e "\n"

# 3. Power-User Trick: Verify the X-Ray sidecar daemon is actively listening for UDP traces on port 2000
bash -c 'echo -n "" > /dev/udp/127.0.0.1/2000 && echo "X-Ray Daemon is actively listening!" || echo "Daemon not reachable"'
```
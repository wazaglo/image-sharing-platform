# Documentation

## Contents

| File              | Description                                                      |
| ----------------- | ---------------------------------------------------------------- |
| `architecture.md` | System architecture overview, data flows, database schema, cost analysis. |
| `deployment.md`   | Step-by-step deployment guide for dev and production environments.      |
| `api.md`          | Complete API reference with request/response schemas and examples.      |
| `security.md`     | Security architecture (IAM, encryption, incident response procedures).  |

---

## Architecture Overview

The platform is fully serverless on AWS with no always-on servers:

| Layer       | Service                   | Role                                    |
| ----------- | ------------------------- | --------------------------------------- |
| **Storage** | S3 + DynamoDB             | File storage + metadata / shares        |
| **Compute** | 6 Lambda (Python 3.11)    | Business logic (CRUD, auth, processing) |
| **API**     | API Gateway (REST)        | HTTP endpoint with Cognito JWT auth     |
| **Auth**    | Cognito User Pool         | Email sign-in, MFA, JWT tokens          |
| **CDN**     | CloudFront                | Static UI delivery + file distribution  |
| **Events**  | EventBridge               | Async thumbnail generation              |
| **Monitor** | CloudWatch + SNS          | Dashboards, alarms, notifications       |

---

## Key Data Flows

1. **File Upload**  
   Client -> API Gateway -> Lambda (generates presigned URL) -> S3 -> EventBridge -> Lambda (thumbnail).

2. **File Download**  
   Client -> API Gateway -> Lambda (generates presigned URL) -> Client reads directly from S3.

3. **Share Access**  
   Client -> CloudFront -> `share.html` -> API Gateway (public endpoints) -> Lambda -> DynamoDB/S3.

4. **WebDAV**  
   Desktop client -> API Gateway (`ANY /webdav/{proxy+}`) -> Lambda (Basic auth -> Cognito token
   exchange) -> DynamoDB/S3.

5. **Authentication**  
   Client -> Cognito (`USER_PASSWORD_AUTH`) -> JWT access token -> API Gateway (Cognito Authorizer) -> Lambda.

---

For details on any of these topics, refer to the specific document listed in the Contents table above.

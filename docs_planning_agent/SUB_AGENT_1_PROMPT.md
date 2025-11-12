# Sub-Agent 1: Infrastructure & Core Setup Agent - Prompt

**Date:** November 11, 2025  
**Agent:** Infrastructure & Core Setup Agent  
**Status:** Ready for Execution  
**Estimated Time:** ~2 hours

---

## Charter

Create the SAM template, AWS infrastructure definitions, project structure, and core configuration files that form the foundation for the Zapier Triggers API MVP serverless REST API on AWS.

---

## Inputs

**Primary Sources of Truth (CRITICAL - Reference Extensively):**
- `PRD_Product_Reqs_v2.md` - Product requirements, endpoint specifications, schemas, error handling
- `PRD_Tech_v2.md` - Technical architecture, SAM requirements, AWS resource specifications, Lambda configurations, DynamoDB schema, S3 configuration, API Gateway setup, IAM roles

**Supporting Documents:**
- `docs_planning_agent/MANUAL_SETUP.md` - AWS resource names, environment configuration, region (`us-east-1`), account details
- `docs_planning_agent/OPEN_QUESTIONS.md` - Resolved implementation decisions (API key format `ak_{32chars}`, tenant_id UUID v4, event_id `evt_{base64url}`, cursor format `{timestamp}_{event_id}`, 30-day TTL, 5-minute leases, etc.)
- `docs_planning_agent/SETUP_AGENT_DONE.md` - Confirms AWS credentials, SAM CLI, Python 3.13.7, Docker all ready

**Key PRD Sections to Reference:**
- **PRD_Tech_v2.md Section 1:** System Architecture Overview (Lambda functions, DynamoDB, S3, API Gateway)
- **PRD_Tech_v2.md Section 2:** Infrastructure Components (SAM template structure, Lambda runtime Python 3.12, timeout 30s)
- **PRD_Tech_v2.md Section 3:** Data Storage (DynamoDB table schemas, partition/sort keys, TTL configuration, S3 bucket lifecycle)
- **PRD_Product_Reqs_v2.md Section 6:** API Endpoints (4 endpoints: POST /events, GET /inbox, POST /inbox/ack, GET /health)
- **PRD_Product_Reqs_v2.md Section 7:** Authentication (API key format, X-API-Key header)

---

## Outputs

**Required Deliverables:**

1. **`template.yaml`** - Complete SAM template with:
   - API Gateway HTTP API configuration (routes, CORS, usage plan: 1000 req/sec, 2000 burst)
   - 4 Lambda functions: `IngestFunction`, `InboxFunction`, `AckFunction`, `HealthFunction`
   - DynamoDB tables: `zapier-triggers-events-{env}` and `zapier-triggers-api-keys-{env}` with correct schemas
   - S3 bucket: `zapier-triggers-events-{env}` with lifecycle rules (30-day deletion)
   - IAM roles and policies (least-privilege access)
   - Environment variable mappings
   - CloudWatch log groups (30-day retention)

2. **`requirements.txt`** - Production Python dependencies:
   - `boto3>=1.34.0`
   - `pydantic>=2.0.0`
   - `aws-lambda-powertools>=2.0.0`

3. **`requirements-dev.txt`** - Development dependencies:
   - `pytest>=7.4.0`
   - `moto>=5.0.0` (AWS mocking)
   - `black>=23.0.0`
   - `pylint>=3.0.0`
   - `pytest-cov>=4.1.0`

4. **`config/dev.yaml`** - Development environment configuration:
   - Table names: `zapier-triggers-events-dev`, `zapier-triggers-api-keys-dev`
   - Bucket name: `zapier-triggers-events-dev`
   - Environment: `dev`
   - Region: `us-east-1`
   - Log level: `INFO`

5. **`config/prod.yaml`** - Production environment configuration:
   - Table names: `zapier-triggers-events-prod`, `zapier-triggers-api-keys-prod`
   - Bucket name: `zapier-triggers-events-prod`
   - Environment: `prod`
   - Region: `us-east-1`
   - Log level: `INFO`

6. **`.github/workflows/deploy.yml`** - CI/CD pipeline:
   - Triggers: Push to `develop` (dev deploy), Push to `main` (prod deploy with approval)
   - Steps: Install dependencies, run tests, validate SAM template, deploy to AWS
   - Uses GitHub secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`

7. **Project Directory Structure:**
   ```
   src/
     lib/
     handlers/
     models/
   tests/
     unit/
     integration/
     load/
   docs/
   config/
   scripts/
   ```

---

## Dependencies

**None** - This is the first sub-agent. Creates the foundation that all other sub-agents depend on.

---

## Key Tasks

1. **Create SAM Template (`template.yaml`):**
   - Define API Gateway HTTP API with 4 routes: POST /events, GET /inbox, POST /inbox/ack, GET /health
   - Configure CORS for Swagger UI origin (from PRD_Tech_v2.md)
   - Set up usage plan: 1000 req/sec, 2000 burst (from PRD_Product_Reqs_v2.md)
   - Define 4 Lambda functions with Python 3.12 runtime, 30-second timeout (from PRD_Tech_v2.md)
   - Configure environment variables for each Lambda (table names, bucket name, region)

2. **Define DynamoDB Tables:**
   - **Events Table:** `zapier-triggers-events-{env}`
     - Partition key: `pk` (String) - Format: `TENANT#{tenant_id}` (from PRD_Tech_v2.md Section 3)
     - Sort key: `sk` (String) - Format: `EVENT#{event_id}#{timestamp}` (from PRD_Tech_v2.md Section 3)
     - Billing: On-Demand
     - TTL attribute: `ttl` (30-day expiration from OPEN_QUESTIONS.md Q5)
   - **API Keys Table:** `zapier-triggers-api-keys-{env}`
     - Partition key: `hashed_key` (String) - SHA-256 hash (from PRD_Tech_v2.md Section 3)
     - Billing: On-Demand

3. **Create S3 Bucket Configuration:**
   - Bucket name: `zapier-triggers-events-{env}` (globally unique)
   - Region: `us-east-1` (from MANUAL_SETUP.md)
   - Block public access: Enabled
   - Encryption: SSE-S3 (default)
   - Lifecycle rule: Delete objects after 30 days (from OPEN_QUESTIONS.md Q5)

4. **Set Up IAM Roles and Policies:**
   - Lambda execution roles (one per function) with least-privilege permissions:
     - DynamoDB read/write permissions (events table, api-keys table)
     - S3 read/write permissions (events bucket)
     - CloudWatch Logs write permissions
   - Reference PRD_Tech_v2.md Section 2 for IAM requirements

5. **Configure Environment Variables:**
   - Map table names, bucket name, region, environment to each Lambda function
   - Use SAM parameter substitution for environment-specific values

6. **Create GitHub Actions Workflow:**
   - File: `.github/workflows/deploy.yml`
   - Triggers: Push to `develop` (auto-deploy dev), Push to `main` (manual approval for prod)
   - Steps: Install Python, install dependencies, run `pytest`, run `sam validate`, run `sam deploy`
   - Use GitHub secrets for AWS credentials

7. **Create Project Directory Structure:**
   - `src/lib/` - Shared libraries (auth, validation, storage, metrics, logging)
   - `src/handlers/` - Lambda handler functions (ingest.py, inbox.py, ack.py, health.py)
   - `src/models/` - Pydantic schema models
   - `tests/unit/` - Unit tests
   - `tests/integration/` - Integration tests
   - `tests/load/` - k6 load test scripts
   - `docs/` - Documentation (OpenAPI spec will go here)
   - `config/` - Environment configuration files
   - `scripts/` - Admin scripts (create_api_key.py)

8. **Create Configuration Files:**
   - `config/dev.yaml` - Development environment settings
   - `config/prod.yaml` - Production environment settings
   - Include: table names, bucket name, region, log level

9. **Create Requirements Files:**
   - `requirements.txt` - Production dependencies (boto3, pydantic, aws-lambda-powertools)
   - `requirements-dev.txt` - Development dependencies (pytest, moto, black, pylint, pytest-cov)

10. **Validate SAM Template:**
    - Run `sam validate` to ensure template syntax is correct
    - Verify all resources are properly defined
    - Check IAM permissions are least-privilege

---

## Success Criteria

**All of the following must be true:**

- ✅ `sam validate` passes without errors
- ✅ SAM template defines all 4 Lambda functions with correct runtime (Python 3.12) and timeout (30s)
- ✅ SAM template defines API Gateway HTTP API with 4 routes matching PRD endpoints
- ✅ SAM template defines 2 DynamoDB tables with correct partition/sort keys matching PRD_Tech_v2.md Section 3
- ✅ SAM template defines S3 bucket with lifecycle rule (30-day deletion)
- ✅ SAM template defines IAM roles with least-privilege permissions
- ✅ Project directory structure matches PRD file layout
- ✅ `requirements.txt` and `requirements-dev.txt` include all required dependencies
- ✅ `config/dev.yaml` and `config/prod.yaml` exist with correct environment-specific values
- ✅ `.github/workflows/deploy.yml` exists with CI/CD pipeline configuration
- ✅ All Lambda functions have environment variables mapped correctly

---

## Implementation Guidelines

**CRITICAL: Reference PRDs Extensively**

- **DynamoDB Schema:** Use PRD_Tech_v2.md Section 3 for exact table schemas, partition/sort key formats
- **Lambda Configuration:** Use PRD_Tech_v2.md Section 2 for runtime (Python 3.12), timeout (30s), memory (256MB default)
- **API Gateway:** Use PRD_Tech_v2.md Section 2 for HTTP API configuration, CORS settings
- **S3 Configuration:** Use PRD_Tech_v2.md Section 3 for bucket naming, lifecycle rules, encryption
- **Environment Naming:** Use `{env}` suffix pattern (dev/prod) as shown in MANUAL_SETUP.md
- **Region:** Use `us-east-1` from MANUAL_SETUP.md and SETUP_AGENT_DONE.md

**Code Quality:**
- Follow Python 3.12 best practices
- Use YAML formatting standards for SAM template
- Ensure all resource names follow naming conventions from PRDs

**Testing:**
- Run `sam validate` before completing
- Verify template structure matches PRD specifications

---

## Notes

- This agent creates the foundation. Do NOT implement Lambda handler logic (that's Sub-Agent 3's job)
- Do NOT create Pydantic schemas (that's Sub-Agent 2's job)
- Focus ONLY on infrastructure, project structure, and configuration files
- Ensure SAM template is production-ready and follows AWS best practices
- Reference OPEN_QUESTIONS.md for resolved decisions (30-day TTL, 5-minute leases, etc.)

---

## Completion Report Format

When you complete your work, provide a summary report that includes:

1. **Status:** ✅ Complete or ⚠️ Partial (with blockers)
2. **Deliverables Created:** List all files created with paths
3. **SAM Validation:** Result of `sam validate` command
4. **Key Decisions:** Any implementation decisions made
5. **Blockers:** Any issues preventing completion
6. **Next Steps:** What Sub-Agent 2/3 need to know

---

**Document Status:** Ready for Sub-Agent 1 Execution  
**Next Step:** Sub-Agent 1 completes infrastructure setup, then Sub-Agent 2 (Auth & Validation) and Sub-Agent 3 (Storage & Handlers) can proceed in parallel


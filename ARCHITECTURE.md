# Flight Record App Architecture

## Overview
This diagram shows how the React frontend and the legacy static HTML page interact with existing AWS components to retrieve and store flight data.

## Mermaid Diagram
```mermaid
flowchart LR
    subgraph Client[User Browsers]
        A1[Legacy HTML Page (Public S3)]
        A2[React SPA (Public S3 / /app prefix)]
    end
    A1 -->|Referer header| WAF
    A2 -->|Referer header (prod) / Injected (dev proxy)| WAF

    subgraph Edge[Security / Entry]
        WAF[WAF WebACL\n- IP allow list\n- Referer starts-with S3 URL\nDefault: Block 401]
        APIGW[API Gateway (FlightRecordAPI / prod)]
    end

    WAF --> APIGW

    subgraph Routes[API Paths]
        POST[POST /retrieve-store-flight-data]
        GET[GET /display-flight-record-table]
    end
    APIGW --> POST
    APIGW --> GET

    subgraph Backend[VPC Components]
        RETRIEVE[Lambda: retrieve-flight-data\nPython 3.9]
        DISPLAY[Lambda: display-flight-record-table\nPython 3.9]
        RDS[(RDS Postgres\nflight_record table)]
    end

    POST --> RETRIEVE
    RETRIEVE -->|Store flight record| RDS

    GET --> DISPLAY
    DISPLAY -->|Query records| RDS

    RETRIEVE -->|External API call| RAPID[(AeroDataBox via RapidAPI)]

    subgraph Dev[Local Development]
        DEV[React Dev Server localhost:3000]
        PROXY[setupProxy.js injects Referer]
    end
    DEV --> PROXY --> WAF

    classDef lambda fill:#fdf6e3,stroke:#b58900;
    classDef storage fill:#eef,stroke:#036;
    class RETRIEVE,DISPLAY lambda
    class RDS storage
```

## ASCII Diagram (Fallback)
```
+----------------------+          +---------------------+          +-------------------+
| Legacy HTML (S3)     |          | React SPA (S3/app)  |          | Local Dev (Proxy) |
+----------+-----------+          +----------+----------+          +----------+--------+
           | Referer (S3 URL)                | Referer (S3 URL)                | Inject Referer
           v                                  v                                v
        +------------------------- WAF WebACL -------------------------------+
        |  Allow: IP Set, Referer starts-with S3 URL  | Default: Block 401   |
        +-----------------------------+---------------+-----------------------+
                                      v
                           +-----------------------+
                           | API Gateway prod      |
                           +-----------+-----------+
                                       |
                +----------------------+--------------------+
                |                                           |
        POST /retrieve-store-flight-data          GET /display-flight-record-table
                |                                           |
        +-------v---------+                       +---------v-------+
        | Lambda retrieve |                       | Lambda display  |
        |  python3.9      |                       |  python3.9      |
        +-------+---------+                       +---------+-------+
                |  External API (RapidAPI AeroDataBox)      |
                v                                           v
        +------------------+                       +------------------+
        |  RDS Postgres     |<---------------------|  (Query flight    |
        | flight_record tbl |                      |   records)        |
        +------------------+                      +------------------+
```

## Component Notes
- S3: Legacy HTML and React build artifacts coexist (React may use /app/ prefix) without changing existing WAF rules.
- WAF: Two explicit allow rules (IP set, Referer) plus custom 401 block response; currently attached to API Gateway.
- API Gateway: Regional; both methods show `authorizationType: NONE`; GET method not requiring API key (`apiKeyRequired: false`).
- Lambdas: Run in VPC, use layers (psycopg2, requests) and environment variables to reach RDS.
- RDS: Stores flight_record data; retrieval Lambda inserts, display Lambda selects.
- RapidAPI: External dependency for flight data enrichment.
- Local Dev: Proxy injects permitted Referer to pass WAF without changing rules.

## Data Flow Summary
1. User submits flight -> POST -> retrieve-flight-data Lambda -> external API call -> RDS insert.
2. User loads records -> GET -> display-flight-record-table Lambda -> RDS select -> JSON response.
3. WAF enforces origin/IP gating before reaching API Gateway.

## Future Evolution (Optional)
- Move WAF to CloudFront if adding CDN layer.
- Add API key or JWT authorizer for stronger auth semantics.
- Introduce caching layer (e.g., DynamoDB or ElastiCache) for frequent record lookup.
- Migrate Referer-based rule to Origin + signed cookies/headers for harder spoofing.

## Legend
- Rectangles: Compute / routing
- Rounded storage: Database
- Parallelogram: External service
- Light yellow boxes: Lambda functions

```diff
+ Minimal-change approach keeps existing S3 static site and WAF rules intact.
```

## AI Agent Path (Bedrock / Strands)

```mermaid
flowchart LR
    subgraph Client[User Browsers]
        SPA[React SPA (talk-to-flight-record)]
    end

    subgraph Edge[API Gateway + Auth]
        APIGW[API Gateway (REST)
        /talk-to-flight-record
        Auth: Cognito JWT
        API key: not required]
    end

    subgraph Lambda[Proxy Layer]
        PROXY[Lambda: proxy-flight-record-bedrock-agent
        python3.12
        Strands SDK + tools]
    end

    subgraph Bedrock[Bedrock]
        MODEL[Claude 3 Haiku
        anthropic.claude-3-haiku-20240307-v1:0]
    end

    subgraph Tools[Data Tools]
        DBTool[Tool: query flight data
        via pg8000 -> RDS]
        MetaTool[Tool: list / summarize records]
    end

    subgraph Data[RDS]
        RDS[(Postgres flight_record)]
    end

    SPA -->|Bearer ID token| APIGW
    APIGW --> PROXY
    PROXY -->|invoke/converse| MODEL
    MODEL --> PROXY
    PROXY --> DBTool
    PROXY --> MetaTool
    DBTool --> RDS
    MetaTool --> RDS
    PROXY -->|answer JSON| SPA

    classDef lambda fill:#fdf6e3,stroke:#b58900;
    classDef storage fill:#eef,stroke:#036;
    class PROXY lambda
    class RDS storage
```

### AI Agent Data Flow Summary
1. React SPA sends POST `/talk-to-flight-record` with question, `Authorization: Bearer <Cognito ID token>`; no `x-api-key` required.
2. API Gateway (REST) authorizes via Cognito, forwards to Lambda `proxy-flight-record-bedrock-agent`.
3. Lambda adds `/package` deps to `sys.path`, builds Strands Agent (Claude 3 Haiku on Bedrock) with Python tools backed by RDS (via `pg8000`).
4. Agent plans, calls tools with `user_sub` to scope queries, and returns structured answer JSON (`answer`, `numbers`, `tool_results`, `plan`).
5. Lambda responds with CORS headers for browser clients.

### AI Agent Component Notes
- Auth: Cognito JWT only; API key not enabled on `/talk-to-flight-record`.
- Model permissions: IAM role `proxy-flight-record-bedrock-agent-role-<suffix>` allows `bedrock:InvokeModel`, `InvokeModelWithResponseStream`, `Converse`, `ConverseStream` on Claude 3 Haiku (us-west-2).
- Dependencies: Strands SDK and tools vendored into `lambdas/talk-to-flight-record/package/`; `sys.path` patched in `handler.py`.
- Tools: Implemented in `tools.py` (invoked via Strands PythonAgentTool wrapper) and access Postgres via `pg8000` using env vars (`DB_HOST`, `DB_NAME`, etc.).
- Responses: Lambda now returns `answer` and `numbers` fields in addition to raw/parsed outputs.
# Architecture and execution flow

## 1. Runtime architecture

```mermaid
flowchart LR
    subgraph UserMachine[Your computer]
        CLI[Command line interface]
        HB[Harness controller]
        CTX[Context builder]
        REG[Tool registry]
        DB[(SQLite notes and tasks)]
        LOG[Metadata logs]
        CLI ==> HB
        HB ==> CTX
        HB ==> REG
        REG ==> DB
        HB ==> LOG
    end
    MODEL[Configured model endpoint]
    CTX ==>|Instructions, profile, recent history, relevant notes| MODEL
    MODEL ==>|Text or structured tool call| HB
    REG ==>|Tool result| HB
    HB ==> CLI
```

The application runs locally. The model request is sent to the endpoint in `.env`. If that endpoint is hosted, the selected prompt, profile, relevant notes, conversation messages, and tool descriptions leave the computer as part of the request. Review the provider's data handling terms before using private information.

## 2. The bounded agent loop

```mermaid
flowchart TD
    A[Receive user request] ==> B[Build a small context]
    B ==> C[Ask model for next response]
    C ==> D{Did it request a tool?}
    D ==>|No| E[Return final answer]
    D ==>|Yes| F{Tool is allowlisted and budget remains?}
    F ==>|No| G[Return a tool error]
    F ==>|Yes| H[Validate tool arguments]
    H ==> I[Execute local tool]
    I ==> J[Append tool result]
    G ==> K{Step limit reached?}
    J ==> K
    K ==>|No| C
    K ==>|Yes| L[Stop with a bounded response]
```

The loop has two independent limits:

- `HARNESS_MAX_STEPS` limits model iterations.
- `HARNESS_MAX_TOOL_CALLS` limits the number of tool calls during a run.

Both are controls. A prompt that says "stop after a few steps" is not enough. The application enforces the limit.

## 3. How a request moves through the five pillars

```mermaid
flowchart TB
    C[1. Context<br/>Instructions, profile, relevant notes] ==> A[2. Action<br/>Approved local tools]
    A ==> O[3. Orchestration<br/>Model and tool loop]
    O ==> K[4. Control<br/>Allowlist, schemas, limits]
    K ==> F[5. Feedback<br/>Logs, tests, user corrections]
    F ==>|Improve prompt, context, tools, or limits| C
```

This diagram is a conceptual view, not a literal execution sequence. Control is checked before tools execute, while feedback is gathered throughout the run.

## 4. Context assembly

```mermaid
flowchart TD
    I[Assistant instructions] ==> X[Current system context]
    P[User profile] ==> X
    H[Recent conversation turns] ==> X
    Q[Current user request] ==> R[Relevant note retrieval]
    R ==> X
    X ==> M[Model request]
```

The assistant does not load every note on every turn. It searches for a few notes with matching terms and includes those as potentially relevant context. This is a deliberately simple retrieval strategy for a small personal database. A larger knowledge base may need full-text search, embeddings, metadata filters, freshness rules, or a dedicated retrieval service.

## 5. Where the engineering disciplines fit

```mermaid
flowchart TB
    PE[Prompt engineering] ==> CI[Instructions and task definition]
    CE[Context engineering] ==> CX[Selected working context]
    LE[Loop engineering] ==> OR[Bounded execution cycle]
    EE[Eval engineering] ==> FB[Quality evidence and regression checks]
    CI ==> HE[Harness engineering]
    CX ==> HE
    OR ==> HE
    FB ==> HE
    HE ==> P[Complete application environment]
    TL[Tools and integrations] ==> P
    CT[Controls and permissions] ==> P
    MM[Memory and state] ==> P
    OB[Observability] ==> P
```

Prompt, context, loop, and eval engineering are distinct areas of practice. Harness engineering is the broader work of integrating them with tools, state, permissions, and runtime behaviour.

# ThinkNote AI — Administrator Flowchart

```mermaid
%%{init: {"flowchart": {"curve": "stepAfter", "nodeSpacing": 40, "rankSpacing": 50}}}%%
flowchart TB
    START([Start]) --> LOGIN[/Log in as Administrator/]
    LOGIN --> VALID{Login successful?}
    VALID -- No --> ERROR[/Show login error/]
    ERROR --> LOGIN
    VALID -- Yes --> DASH[Open administrator dashboard]
    DASH --> ACTION{Choose an action}

    subgraph ANALYTICS["Platform Analytics"]
        direction TB
        LOAD[Load analytics overview]
        METRICS[/Display users, videos, completed and published lectures/]
        QUALITY[/Display average ROUGE-1, ROUGE-2, and ROUGE-L scores/]

        LOAD --> METRICS
        METRICS --> QUALITY
        QUALITY --> DASH
    end

    subgraph USERS["User Oversight"]
        direction TB
        USER_LIST[Load registered users]
        USER_OUTPUT[/Display name, email, role, status, and creation date/]
        USER_OUTPUT --> DASH
        USER_LIST --> USER_OUTPUT
    end

    subgraph CATALOG["Video and Result Oversight"]
        direction TB
        VIDEOS[Load institution video catalog]
        FILTER[/Search or filter videos by status/]
        SELECT[/Select a video/]
        VIDEO_ACTION{Choose an action}
        REVIEW[Review video metadata and processing status]
        RESULTS[Inspect transcript, captions, summaries, slides, and evaluation]
        CHAT[/Ask the lecture AI a question/]
        ANSWER[Generate answer from lecture content]
        ASSIGN_TYPE{Assign video to whom?}
        ONE[/Enter student email/]
        COURSE_STUDENTS[Assign to registered course students]
        ALL_STUDENTS[Assign to all active students]
        CONFIRM[/Display assignment result/]

        VIDEOS --> FILTER
        FILTER --> SELECT
        SELECT --> VIDEO_ACTION
        VIDEO_ACTION -- Review record --> REVIEW
        REVIEW --> VIDEOS
        VIDEO_ACTION -- Inspect results --> RESULTS
        RESULTS --> CHAT
        CHAT --> ANSWER
        ANSWER --> RESULTS
        VIDEO_ACTION -- Assign --> ASSIGN_TYPE
        ASSIGN_TYPE -- One student --> ONE
        ASSIGN_TYPE -- Course students --> COURSE_STUDENTS
        ASSIGN_TYPE -- All students --> ALL_STUDENTS
        ONE --> CONFIRM
        COURSE_STUDENTS --> CONFIRM
        ALL_STUDENTS --> CONFIRM
        CONFIRM --> VIDEOS
    end

    ACTION -- View analytics --> LOAD
    ACTION -- View users --> USER_LIST
    ACTION -- Review videos --> VIDEOS
    ACTION -- Log out --> END([End])

    classDef terminal fill:#d5f5e3,stroke:#1e8449,stroke-width:2px,color:#17202a;
    classDef process fill:#d6eaf8,stroke:#2471a3,stroke-width:1.5px,color:#17202a;
    classDef decision fill:#fcf3cf,stroke:#b7950b,stroke-width:1.5px,color:#17202a;
    classDef io fill:#f5eef8,stroke:#7d3c98,stroke-width:1.5px,color:#17202a;

    class START,END terminal;
    class DASH,LOAD,USER_LIST,VIDEOS,REVIEW,RESULTS,ANSWER,COURSE_STUDENTS,ALL_STUDENTS process;
    class VALID,ACTION,VIDEO_ACTION,ASSIGN_TYPE decision;
    class LOGIN,ERROR,METRICS,QUALITY,USER_OUTPUT,FILTER,SELECT,CHAT,ONE,CONFIRM io;

    style ANALYTICS fill:#fef9e7,stroke:#d4ac0d
    style USERS fill:#f4ecf7,stroke:#a569bd
    style CATALOG fill:#ebf5fb,stroke:#5dade2
```

## Symbol Key

- Oval: start or end.
- Rectangle: process or system action.
- Diamond: decision.
- Parallelogram: input or output.
- Arrow: flow direction.

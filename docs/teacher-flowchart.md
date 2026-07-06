# ThinkNote AI — Teacher Flowcharts

The teacher module is divided into an overview and three detailed sub-processes.
This academic decomposition keeps each diagram readable and prevents crossing
flowlines.

## 1. Teacher Module Overview

```mermaid
%%{init: {"flowchart": {"curve": "linear", "nodeSpacing": 42, "rankSpacing": 58}}}%%
flowchart TB
    START([Teacher starts]) --> LOGIN[/Sign up or log in/]
    LOGIN --> AUTH{Authenticated as teacher?}
    AUTH -- No --> REDIRECT[Redirect to permitted role dashboard]
    REDIRECT --> END([End])
    AUTH -- Yes --> DASH[Teacher dashboard]
    DASH --> WORKSPACE[Select active course workspace]
    WORKSPACE --> MENU{Choose menu action}

    MENU -- Home --> DASH
    MENU -- Add course --> CREATE_COURSE[/Enter new course workspace name/]
    CREATE_COURSE --> COURSE_VALID{Name valid?}
    COURSE_VALID -- No --> COURSE_ERROR[/Display workspace validation error/]
    COURSE_ERROR --> CREATE_COURSE
    COURSE_VALID -- Yes --> SAVE_COURSE[Create new course workspace]
    SAVE_COURSE --> WORKSPACE

    MENU -- Upload lecture --> OPEN_UPLOAD[Open upload workspace]
    OPEN_UPLOAD --> SOURCE{Video source}
    SOURCE -- Local file --> LOCAL_FILE[/Choose lecture video file/]
    SOURCE -- YouTube --> YOUTUBE_URL[/Enter supported YouTube URL/]
    LOCAL_FILE --> DETAILS[/Enter title, course, module, description, visibility, and reference summary/]
    YOUTUBE_URL --> DETAILS
    DETAILS --> INPUT_VALID{Input valid?}
    INPUT_VALID -- No --> INPUT_ERROR[/Display upload validation error/]
    INPUT_ERROR --> DETAILS
    INPUT_VALID -- Yes --> CREATE_VIDEO[Create video record and processing job]
    CREATE_VIDEO --> PIPELINE[Run multimodal AI pipeline]
    PIPELINE --> AUDIO[Extract audio]
    AUDIO --> TRANSCRIPT[Generate transcript]
    TRANSCRIPT --> FRAMES[Extract and analyze frames]
    FRAMES --> FUSION[Fuse transcript and visual content]
    FUSION --> CLEAN[Clean NLP content]
    CLEAN --> SUMMARY[Generate summaries and evaluate with ROUGE]
    SUMMARY --> PIPELINE_DONE{Pipeline completed?}
    PIPELINE_DONE -- No --> FAILED[/Show failed stage and error/]
    FAILED --> MENU
    PIPELINE_DONE -- Yes --> READY[/Transcript, captions, summaries, and scores are ready/]
    READY --> RESULTS_PAGE[Open AI results]

    MENU -- Results --> RESULTS_PAGE
    RESULTS_PAGE --> SELECT_RESULT[/Select one of teacher videos/]
    SELECT_RESULT --> REVIEW_SUMMARY[Review structured summary]
    REVIEW_SUMMARY --> REVIEW_TRANSCRIPT[Review transcript and fused multimodal text]
    REVIEW_TRANSCRIPT --> REVIEW_ROUGE[Review ROUGE quality scores]
    REVIEW_ROUGE --> LIBRARY_PAGE

    MENU -- Videos --> LIBRARY_PAGE[Open my lecture library]
    LIBRARY_PAGE --> LIBRARY_ACTION{Choose library action}

    LIBRARY_ACTION -- Review requests --> REQUESTS[Review student course requests]
    REQUESTS --> REQUEST_DECISION{Teacher decision}
    REQUEST_DECISION -- Accept --> ACCEPT[Student receives full published course access]
    REQUEST_DECISION -- Reject --> REJECT[Course request marked rejected]
    ACCEPT --> LIBRARY_PAGE
    REJECT --> LIBRARY_PAGE

    LIBRARY_ACTION -- Manage videos --> FILTER[/Search and filter own videos in active workspace/]
    FILTER --> VIDEO_ACTION{Choose management action}
    VIDEO_ACTION -- Preview --> STREAM[Stream lecture]
    STREAM --> LIBRARY_PAGE
    VIDEO_ACTION -- Assign --> ASSIGN_SCOPE{Assignment scope}
    ASSIGN_SCOPE -- One student --> STUDENT_EMAIL[/Enter active student email/]
    ASSIGN_SCOPE -- Accepted course students --> COURSE_STUDENTS[Assign to all accepted students in course]
    ASSIGN_SCOPE -- All students --> ALL_STUDENTS[Assign to all students]
    STUDENT_EMAIL --> PUBLISH[Publish video and create assignment]
    COURSE_STUDENTS --> PUBLISH
    ALL_STUDENTS --> PUBLISH
    PUBLISH --> LIBRARY_PAGE

    MENU -- Logout --> LOGOUT[Clear session and return to login]
    LOGOUT --> END

    classDef terminal fill:#f0eaff,stroke:#a78bfa,stroke-width:2px,color:#2f255f;
    classDef process fill:#f3f0ff,stroke:#a78bfa,stroke-width:1.5px,color:#2f255f;
    classDef decision fill:#f8f5ff,stroke:#a78bfa,stroke-width:1.5px,color:#2f255f;
    classDef io fill:#f6f2ff,stroke:#a78bfa,stroke-width:1.5px,color:#2f255f;

    class START,END terminal;
    class REDIRECT,DASH,WORKSPACE,SAVE_COURSE,OPEN_UPLOAD,CREATE_VIDEO,PIPELINE,AUDIO,TRANSCRIPT,FRAMES,FUSION,CLEAN,SUMMARY,RESULTS_PAGE,REVIEW_SUMMARY,REVIEW_TRANSCRIPT,REVIEW_ROUGE,LIBRARY_PAGE,REQUESTS,ACCEPT,REJECT,STREAM,COURSE_STUDENTS,ALL_STUDENTS,PUBLISH,LOGOUT process;
    class AUTH,MENU,COURSE_VALID,SOURCE,INPUT_VALID,PIPELINE_DONE,LIBRARY_ACTION,REQUEST_DECISION,VIDEO_ACTION,ASSIGN_SCOPE decision;
    class LOGIN,CREATE_COURSE,COURSE_ERROR,LOCAL_FILE,YOUTUBE_URL,DETAILS,INPUT_ERROR,FAILED,READY,SELECT_RESULT,FILTER,STUDENT_EMAIL io;
```

## 2. Course and Student Management

```mermaid
%%{init: {"flowchart": {"curve": "linear", "nodeSpacing": 40, "rankSpacing": 50}}}%%
flowchart TB
    START([Begin]) --> OPERATION{Select operation}

    OPERATION -- Manage workspaces --> WORKSPACES[Display course workspaces]
    WORKSPACES --> CREATE{Create workspace?}
    CREATE -- No --> FINISH
    CREATE -- Yes --> NAME[/Enter workspace name/]
    NAME --> VALID{Name valid?}
    VALID -- No --> NAME_ERROR[/Display validation error/]
    NAME_ERROR --> NAME
    VALID -- Yes --> SAVE[Save course workspace]
    SAVE --> CONFIRM[/Display confirmation/]
    CONFIRM --> FINISH

    OPERATION -- Review requests --> REQUESTS[Display registration requests]
    REQUESTS --> AVAILABLE{Pending request available?}
    AVAILABLE -- No --> NONE[/Display no pending requests/]
    NONE --> FINISH
    AVAILABLE -- Yes --> SELECT[/Select request/]
    SELECT --> DECISION{Teacher decision}
    DECISION -- Accept --> ACCEPT[Grant course access]
    DECISION -- Reject --> REJECT[Reject course access]
    ACCEPT --> RESULT[/Display updated status/]
    REJECT --> RESULT
    RESULT --> FINISH

    FINISH([Return to dashboard])

    classDef terminal fill:#d5f5e3,stroke:#1e8449,stroke-width:2px,color:#17202a;
    classDef process fill:#d6eaf8,stroke:#2471a3,stroke-width:1.5px,color:#17202a;
    classDef decision fill:#fcf3cf,stroke:#b7950b,stroke-width:1.5px,color:#17202a;
    classDef io fill:#f5eef8,stroke:#7d3c98,stroke-width:1.5px,color:#17202a;

    class START,FINISH terminal;
    class WORKSPACES,SAVE,REQUESTS,ACCEPT,REJECT process;
    class OPERATION,CREATE,VALID,AVAILABLE,DECISION decision;
    class NAME,NAME_ERROR,CONFIRM,NONE,SELECT,RESULT io;
```

## 3. Lecture Upload and AI Processing

```mermaid
%%{init: {"flowchart": {"curve": "linear", "nodeSpacing": 40, "rankSpacing": 50}}}%%
flowchart TB
    START([Begin]) --> SOURCE{Select video source}
    SOURCE -- Local file --> LOCAL[/Select video file/]
    SOURCE -- YouTube --> URL[/Enter YouTube URL/]
    LOCAL --> DETAILS
    URL --> DETAILS

    DETAILS[/Enter lecture details and reference summary/] --> VALID{Input valid?}
    VALID -- No --> INPUT_ERROR[/Display validation error/]
    INPUT_ERROR --> DETAILS
    VALID -- Yes --> STORE[Save video and lecture record]
    STORE --> JOB[Create processing job]
    JOB --> SUBTITLES{Subtitles available?}

    SUBTITLES -- Yes --> PARSE[Parse subtitle transcript]
    SUBTITLES -- No --> AUDIO[Extract audio with FFmpeg]
    AUDIO --> WHISPER[Transcribe audio with Whisper]
    PARSE --> TRANSCRIPT[Store transcript and timestamps]
    WHISPER --> TRANSCRIPT

    TRANSCRIPT --> FRAMES[Extract educational keyframes]
    FRAMES --> VISION[Analyze OCR, visuals, and equations]
    VISION --> FUSION[Fuse speech and visual evidence]
    FUSION --> NLP[Clean content and remove repetition]
    NLP --> SUMMARY[Generate lecture and slide summaries]
    SUMMARY --> EVALUATE[Calculate ROUGE scores]
    EVALUATE --> SUCCESS{Processing successful?}

    SUCCESS -- No --> FAILED[Set lecture status to failed]
    FAILED --> FAILURE[/Display processing failure/]
    FAILURE --> FINISH

    SUCCESS -- Yes --> COMPLETE[Save results and mark completed]
    COMPLETE --> REVIEW[/Display generated results/]
    REVIEW --> DISTRIBUTE{Publish and assign?}
    DISTRIBUTE -- No --> DRAFT[Keep lecture in teacher library]
    DISTRIBUTE -- Yes --> METHOD{Select assignment method}
    METHOD -- One student --> STUDENT[/Enter student email/]
    METHOD -- Course students --> REGISTERED[Assign to registered students]
    METHOD -- All students --> ALL[Assign to all active students]
    STUDENT --> PUBLISH[Publish and save assignment]
    REGISTERED --> PUBLISH
    ALL --> PUBLISH
    DRAFT --> FINISH
    PUBLISH --> FINISH

    FINISH([Return to dashboard])

    classDef terminal fill:#d5f5e3,stroke:#1e8449,stroke-width:2px,color:#17202a;
    classDef process fill:#d6eaf8,stroke:#2471a3,stroke-width:1.5px,color:#17202a;
    classDef decision fill:#fcf3cf,stroke:#b7950b,stroke-width:1.5px,color:#17202a;
    classDef io fill:#f5eef8,stroke:#7d3c98,stroke-width:1.5px,color:#17202a;
    classDef failure fill:#fadbd8,stroke:#c0392b,stroke-width:1.5px,color:#17202a;

    class START,FINISH terminal;
    class STORE,JOB,PARSE,AUDIO,WHISPER,TRANSCRIPT,FRAMES,VISION,FUSION,NLP,SUMMARY,EVALUATE,COMPLETE,DRAFT,REGISTERED,ALL,PUBLISH process;
    class SOURCE,VALID,SUBTITLES,SUCCESS,DISTRIBUTE,METHOD decision;
    class LOCAL,URL,DETAILS,INPUT_ERROR,FAILURE,REVIEW,STUDENT io;
    class FAILED failure;
```

## 4. Existing Lecture Management

```mermaid
%%{init: {"flowchart": {"curve": "linear", "nodeSpacing": 40, "rankSpacing": 50}}}%%
flowchart TB
    START([Begin]) --> LIBRARY[Display lecture library]
    LIBRARY --> FILTER[/Search or filter lectures/]
    FILTER --> SELECT[/Select lecture/]
    SELECT --> ACTION{Select operation}

    ACTION -- Processing status --> STATUS[Retrieve processing status]
    STATUS --> STATUS_OUTPUT[/Display stage and progress/]
    STATUS_OUTPUT --> FINISH

    ACTION -- Review results --> RESULTS[Retrieve generated results]
    RESULTS --> RESULT_OUTPUT[/Display video, transcript, slides, summary, and scores/]
    RESULT_OUTPUT --> CHAT{Ask a question?}
    CHAT -- Yes --> QUESTION[/Enter lecture question/]
    QUESTION --> ANSWER[Generate answer from lecture content]
    ANSWER --> RESULT_OUTPUT
    CHAT -- No --> FINISH

    ACTION -- Assign lecture --> METHOD{Select assignment method}
    METHOD -- One student --> STUDENT[/Enter student email/]
    METHOD -- Course students --> REGISTERED[Assign to registered students]
    METHOD -- All students --> ALL[Assign to all active students]
    STUDENT --> ASSIGNED[/Display assignment confirmation/]
    REGISTERED --> ASSIGNED
    ALL --> ASSIGNED
    ASSIGNED --> FINISH

    ACTION -- Delete lecture --> CONFIRM{Confirm deletion?}
    CONFIRM -- No --> FINISH
    CONFIRM -- Yes --> DELETE[Delete record and stored artifacts]
    DELETE --> DELETED[/Display deletion confirmation/]
    DELETED --> FINISH

    FINISH([Return to dashboard])

    classDef terminal fill:#d5f5e3,stroke:#1e8449,stroke-width:2px,color:#17202a;
    classDef process fill:#d6eaf8,stroke:#2471a3,stroke-width:1.5px,color:#17202a;
    classDef decision fill:#fcf3cf,stroke:#b7950b,stroke-width:1.5px,color:#17202a;
    classDef io fill:#f5eef8,stroke:#7d3c98,stroke-width:1.5px,color:#17202a;

    class START,FINISH terminal;
    class LIBRARY,STATUS,RESULTS,ANSWER,REGISTERED,ALL,DELETE process;
    class ACTION,CHAT,METHOD,CONFIRM decision;
    class FILTER,SELECT,STATUS_OUTPUT,RESULT_OUTPUT,QUESTION,STUDENT,ASSIGNED,DELETED io;
```

## Symbol Key

- Oval: start, end, or return point.
- Rectangle: process or system operation.
- Diamond: decision or conditional branch.
- Parallelogram: user input or system output.
- Double-lined rectangle: referenced sub-process.
- Arrow: execution direction.

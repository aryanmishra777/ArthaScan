# ArthaScan System Architecture

This top-down architecture diagram illustrates the entire flow of the mutual fund verification engine. It isolates the LLM from the mathematical logic, ensuring a "Zero-Hallucination" operation for processing investor wealth.

```mermaid
graph TD
    %% User Inputs
    User((User)) -->|Uploads PDF Statement\nvia Telegram| TBot[Telegram Bot Interface]
    User -->|Sends Free-Text Chat| Router[Intent Router / Chat Guard]

    %% Extraction Pipeline (Multimodal + Fallbacks)
    subgraph Data Extraction Pipeline
        TBot -->|Sends PDF| ImageRasterizer[PyMuPDF Rasterizer]
        ImageRasterizer -->|Sends 200 DPI PNGs| Vision[Gemini 2.5 Vision LLM]
        Vision -->|Extracts raw JSON| Pydantic[Pydantic JSON Validator]
        
        Pydantic -- Invalid JSON --> Repair[Self-Healing LLM Loop]
        Repair --> Pydantic
        
        Pydantic -- Valid JSON --> StructuredData[(Structured Payload)]
        
        ImageRasterizer -- Timeout / API Fail --> RegexMatcher[Regex Fallback Parser]
        RegexMatcher --> StructuredData
    end

    %% Deterministic Mathematical Engine
    subgraph Deterministic Finance Engine 
        StructuredData --> Metrics[metrics.py]
        Metrics --> XIRR[Binary Search XIRR]
        Metrics --> Overlap[Portfolio Asset Overlap]
        Metrics --> Health[0-100 Health Score Calc]
        
        XIRR --> FinancialTruth{Aggregated Metrics}
        Overlap --> FinancialTruth
        Health --> FinancialTruth
    end

    %% Strict Business Rules Engine
    subgraph Decision Engine
        FinancialTruth --> Rules[rules.py]
        Rules --> Actions{Final Actions}
        Actions -->|Overlap > 60%| Consolidate([CONSOLIDATE])
        Actions -->|Poor Alpha + High TER| Sell([SELL])
        Actions -->|Closet Index Tracking| Switch([SWITCH to Direct Fund])
        Actions -->|Good Performance| Keep([KEEP])
    end

    %% Glass-Box AI Presentation Layer
    subgraph Conversational Layer
        Actions --> PDFGen[ReportLab PDF Generator]
        PDFGen --> TBot
        
        Router -- Mathematical Query --> DeterministicResponse[Hardcoded Answer]
        Router -- General Query --> GuardedLLM[Guarded Gemini Explainer]
        Router -- Repeated Query --> Cache[(RAM Caching)]
        
        GuardedLLM -->|Translates to Hinglish/English| TBot
        DeterministicResponse --> TBot
        Cache --> TBot
    end

    %% Theming
    classDef llm fill:#bb86fc,stroke:#fff,stroke-width:2px,color:#000;
    classDef logic fill:#03dac6,stroke:#fff,stroke-width:2px,color:#000;
    classDef fail-safe fill:#cf6679,stroke:#fff,stroke-width:2px,color:#000;
    classDef action fill:#ffb74d,stroke:#fff,stroke-width:2px,color:#000;
    
    class Vision,Repair,GuardedLLM llm;
    class Metrics,XIRR,Overlap,Health,Rules logic;
    class RegexMatcher fail-safe;
    class Consolidate,Sell,Switch action;
```

### Color Guide
- **Purple nodes:** LLM operations (Vision extraction and Chat generation)
- **Teal nodes:** Pure Python deterministic mathematical engines (100% hallucination-free)
- **Red nodes:** Silent fail-safe / fallback parsers if the API limits out
- **Orange nodes:** Final rigid decision outputs

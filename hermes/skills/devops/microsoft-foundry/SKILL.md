---
name: microsoft-foundry
description: "Microsoft AI Foundry (409.2K installs) — Microsoft's unified AI platform for building, evaluating, and deploying foundation models. Covers model catalog, fine-tuning, prompt flow, safety evaluation, and deployment."
version: 1.0.0
author: Hermes Agent
tags: [microsoft, AI, foundry, azure, foundation-models, LLM, deployment, fine-tuning]
---

# Microsoft AI Foundry

Microsoft's AI Foundry platform (409.2K installs on skills.sh, published by microsoft/azure-skills).

## Installation
```bash
npx skills add microsoft/azure-skills
# Contains: microsoft-foundry, azure-ai, azure-compute, azure-cloud-migrate, 
#           azure-quotas, azure-hosted-copilot-sdk
```

## Key Capabilities
- **Model Catalog** — Browse and select foundation models (GPT-4, Llama, Mistral, Phi, etc.)
- **Fine-tuning** — Customize models with training data
- **Prompt Flow** — Orchestrate LLM pipelines with evaluation
- **Safety Evaluation** — Content safety, jailbreak detection, groundedness checks
- **Deployment** — Serverless, managed compute, real-time endpoints
- **RAG Patterns** — Azure AI Search integration, vector indexing

## Integration with Hermes Skills
- `azure-cloud-skills` — our umbrella for Azure (Compute, Migration, Quotas, AI)
- `local-llm-workbench` — local LLM deployment alternative
- `huggingface-spaces` — HF Spaces deployment alternative

## Workflow
1. Browse model catalog via Azure AI Studio
2. Select base model + configure inference
3. Fine-tune with custom data if needed
4. Set up content safety filters
5. Deploy to serverless endpoint
6. Connect via OpenAI-compatible API

> Source: skills.sh — microsoft/azure-skills (6.1M total installs across 7 skills)

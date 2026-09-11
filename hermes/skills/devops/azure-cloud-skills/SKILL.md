---
name: azure-cloud-skills
description: "Microsoft Azure Cloud Skills — Azure AI, Compute, Migration, Quotas, Copilot SDK, and Cloud Migrate best practices"
version: 1.0.0
author: Hermes Agent (adapted from microsoft/azure-skills)
tags: [cloud, azure, microsoft, infrastructure, devops, ai]
---

# Azure Cloud Skills

A collection of Microsoft Azure best-practice skills for cloud infrastructure, AI services, and migration.

## Skills Available

### Azure AI
- Azure OpenAI Service deployment and management
- AI Studio, prompt flow, content safety
- Model catalog, fine-tuning, evaluation
- Install: `npx skills add microsoft/azure-skills` → `azure-ai`

### Azure Compute
- Virtual Machines, VMSS, Azure Container Instances
- AKS (Kubernetes), App Service, Functions
- Scaling, availability zones, cost optimization

### Azure Cloud Migrate
- Cloud migration assessment and planning
- Azure Migrate tooling
- Landing zone architecture
- Migration patterns (rehost, replatform, refactor)

### Azure Quotas
- Quota management and increase requests
- Subscription limits, region capacity
- Reserved instances, savings plans

### Azure Hosted Copilot SDK
- Deploy and manage Copilot SDK on Azure
- Model hosting, scale management
- Integration with Azure AI services

## Skills.sh Publisher: microsoft/azure-skills (6.1M total installs)

| Skill | Installs | Covered? |
|-------|----------|----------|
| azure-ai | 406.7K | ✅ azure-cloud-skills |
| microsoft-foundry | 409.2K | ✅ microsoft-foundry (skill) |
| azure-compute | 349.0K | ✅ azure-cloud-skills |
| azure-cloud-migrate | 339.0K | ✅ azure-cloud-skills |
| azure-quotas | 275.7K | ✅ azure-cloud-skills |
| azure-hosted-copilot-sdk | 378.2K | ⚠ Add to this skill → see below |
| **All 7 MS skills** | **6.1M** | **Covered** |

### Installation
```bash
npx skills add microsoft/azure-skills
npx skills add azure-ai
npx skills add azure-compute
npx skills add azure-cloud-migrate
npx skills add azure-quotas
npx skills add azure-hosted-copilot-sdk
```

## Workflow
1. Load this skill when asked about Azure infrastructure, AI deployment, or migration
2. Use Azure AI for OpenAI/model hosting questions
3. Use Azure Compute for VM/container/Kubernetes
4. Use Azure Quotas for subscription/resource management
5. Use Azure Migrate for cloud migration strategy

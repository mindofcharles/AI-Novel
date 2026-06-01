# AI Autonomy Suite: ATT (AI Team Team) Topology

Welcome to the technical specifications and architectural guide for the **ATT (AI Team Team) Autonomy Suite** in the AI-Novel generator.

This directory contains deep-dive design guides, parameters, and operation specs for each module of our self-governing multi-agent framework.

## Document Directory

To understand specific systems in detail, please refer to the following documents:

1. **[Hierarchical Dynamic Delegation](Dynamic_Delegation.md)**: Explains the recursive `Agent` and `AgentTeam` lineages (Level 0 Root AI spawning Level 1 ATs, who spawn Level 2 ATs), ReAct execution loops with safe literal evaluation, and the lineage escalation channels.
2. **[Gated Context Protection & File Reading](Gated_Reading.md)**: Details the size-aware `GatedFileReader`, outline sampling fallbacks for files exceeding 50 KB, paginated line chunking, and streaming tail log reads.
3. **[Supervisor Auditor Team](Supervisory_Team.md)**: Details the dynamic **3-AI Supervisory Team** (Integrity, Continuity, and Deadlock Auditors) which monitors dialogue transcripts for circular deadlocks and performs recursive lineage parent escalations.

## Core Architecture Overview

The ATT Topology transitions AI agents from passive context-consumers to active, collaborative team groups. It is built on a recursive team model coordinated by the master `ATTManager`:

```plaintext
                     ┌──────────────────────────────┐
                     │    Supervisory Auditor Team  │
                     │       (Exactly 3 AIs)        │
                     └──────────────┬───────────────┘
                                    │ Audits Dialogue Logs
                                    ▼
                     ┌──────────────────────────────┐
                     │         ATT Manager          │
                     └──────────────┬───────────────┘
                                    │ Coordinates Lineages
                      ┌─────────────┴─────────────┐
                      ▼                           ▼
         ┌────────────────────────┐   ┌────────────────────────┐
         │    Agent Team (AT)     │   │    Agent Team (AT)     │
         │      (Size N >= 3)     │   │      (Size N >= 3)     │
         └────────────────────────┘   └────────────────────────┘
```

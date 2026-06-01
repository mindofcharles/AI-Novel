# Supervisory Team Audits & Parent Escalations Flowchart

This document details the dialogue auditing logic and the recursive lineage escalation protocol executed by the **Supervisory Team**.

## 1. 3-AI Dialogue Auditing Logic Flowchart

This flowchart outlines the sequence executed on every dynamic debate turn or discussion session to verify overall dialogue health:

```mermaid
flowchart TD
    Start["Call audit_team_dialog(team, transcript)"] --> FormulatePrompt["Assemble Audit Prompt containing\nthe multi-agent debate transcript"]
    
    FormulatePrompt --> BatchCall["Run 3-AI Auditor consensus check\n(Single batch LLM JSON call)"]
    
    BatchCall --> ParseResponse{"Parse health evaluation JSON\n{'is_healthy': bool, 'reason': str}"}
    
    ParseResponse -- "Parse Fails" --> FallbackHealthy["Log parse error\nDefault health to True"]
    ParseResponse -- "Parse Success" --> HealthGate{"is_healthy == True?"}
    
    HealthGate -- "Yes" --> End["Discussion healthy (No intervention needed)"]
    FallbackHealthy --> End
    
    HealthGate -- "No (Anomaly Detected)" --> TriggerEscalation["Call report_anomaly(failed_team, reason, manager)"]
    TriggerEscalation --> EscalationFlow["Execute Parent Escalation Tree"]
```

## 2. Parent-Ancestor Escalation Tree Flowchart

This flowchart visualizes the recursive lineage climbing checks executed by `SupervisoryTeam.report_anomaly` to resolve failures or report alerts:

```mermaid
flowchart TD
    StartClimb["Initialize failed_team, failed_lineage = [failed_team]"] --> ResolveParent["Get current_parent\n(Traverse parent_team or find_parent_team)"]
    
    ResolveParent --> ParentExists{"current_parent exists?"}
    
    ParentExists -- "Yes" --> AuditParent["Audit the parent team itself:\naudit_team_dialog(current_parent, 'escalation')"]
    
    AuditParent --> ParentHealthy{"Parent is healthy?"}
    
    ParentHealthy -- "Yes" --> RouteAlert["Route failure alert payload to Parent inbox:\n- failed_team_id\n- reason\n- type: child_failure_escalation"]
    RouteAlert --> ParentPrepend["Parent injects alert into its next active discussion prompt"]
    ParentPrepend --> End["Escalation resolved successfully"]
    
    ParentHealthy -- "No" --> LogBrokenParent["Log parent failure\nAppend current_parent to failed_lineage\nSet failed_team = current_parent"]
    LogBrokenParent --> ResolveParent
    
    ParentExists -- "No (Ancestry Tree Collapsed)" --> AlertRootAI["Escalate critical warning directly to Root AI Level 0"]
    AlertRootAI --> RootAlert["Display Critical Warning log\n(Root AI handles architectural correction)"]
    RootAlert --> End
```

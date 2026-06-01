# Negotiation Broker & Sibling Routing Flowchart

This document details the dynamic P2P sibling and cross-lineage communication permissions negotiated by the `NegotiationBroker` under the ATT framework.

## 1. Sequence of Tools Context Registration & Team Spawning

This sequence diagram outlines the registration of system-wide dependencies and automatic tools binding during dynamic team spawning:

```mermaid
sequenceDiagram
    autonumber
    participant Mixin as AutonomyWorkflowMixin
    participant Manager as ATTManager
    participant Team as AgentTeam
    
    Mixin->>Manager: register_tools_context(context)
    Note over Manager: Save SQLite DB, Vector Store, Gated Reader context
    
    Mixin->>Manager: create_agent_team(creator, member_count=3)
    Note over Manager: Spawn AgentTeam with Creator (Agent/Team)
    Manager->>Team: Instantiate AgentTeam (N >= 3)
    Manager->>Manager: get_default_tools(tools_context, Team)
    Manager->>Team: Bind registered Tools dictionary
    Manager-->>Mixin: Return dynamic AgentTeam bound with Centralized Tools
```

## 2. Sibling & Cross-Lineage Negotiation Flowchart

This flowchart outlines the gating logic executed inside `NegotiationBroker.negotiate_communication` when a dynamic team attempts to establish a communication tunnel with a peer:

```mermaid
flowchart TD
    Start["Call negotiate_communication(sender, recipient, mode)"] --> GetParents["Resolve sender_parent and recipient_parent\n(Traverse tree creator links)"]
    
    GetParents --> SiblingCheck{"sender_parent == recipient_parent?\n(Sibling Team Check)"}
    
    SiblingCheck -- "Yes (Sibling ATs)" --> ParentSiblingTalk{"Parent rules set\nallow_sibling_talk == True?"}
    ParentSiblingTalk -- "Yes" --> ApproveSibling["Approve Sibling Talk (return True)"]
    ParentSiblingTalk -- "No" --> DenySibling["Deny Sibling Talk (return False)"]
    
    SiblingCheck -- "No (Cross-Lineage ATs)" --> ParentLineageCheck{"Respective parent teams exist?"}
    
    ParentLineageCheck -- "No (Incomplete lineage)" --> DenyCross["Deny communication (return False)"]
    ParentLineageCheck -- "Yes" --> ParentAgreementDebate["Run _run_parent_negotiation_loop\n(Agreement debate between parent teams)"]
    
    ParentAgreementDebate --> SupportedMode{"Negotiation mode is supported?\n('proxied' | 'indirect' | 'rule_gated')"}
    SupportedMode -- "Yes" --> ApproveCross["Establish cross-lineage communication tunnel (return True)"]
    SupportedMode -- "No" --> DenyCross
```

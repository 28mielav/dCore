# Denizen and DenizenM engineering

## Containers and control flow

Identify every script container and its entry points before editing. Distinguish world events, tasks, commands, assignments, procedures, and data. Keep definitions queue-local unless cross-queue lifetime is intended. Treat `run`, `inject`, waits, loops, and callbacks as queue/lifetime boundaries; trace their caller, owner, cancellation, and error path.

Never infer that a plausible tag or mechanism exists. Resolve it against target-pinned Meta. For addons, identify the provider and exact artifact. Reflect syntax passing a parser does not prove a Java method, field, signature, classloader, or thread rule.

## Events

For each event, record:

- exact event line and target version;
- switches and matcher scope;
- context objects and their types;
- cancellation/determination behavior;
- frequency and hot-path cost;
- re-entry/duplication risk;
- ownership of spawned queues, entities, flags, and tasks.

Prefer narrow event matchers and early guards. Do not put database, file, network, broad entity scans, or repeated Meta resolution in a high-frequency event without an explicit budget.

## Tags and mechanisms

Treat tag output as a typed value. Track list/map/scalar/object/null/error flow through chained tags. Validate mechanisms against the target object type and build. When a value crosses a command, flag, YAML, storage, or script boundary, define serialization and missing-value behavior.

## Queue and flag lifecycles

A queue owns its definitions and wait state. A flag owns data for the lifetime of its holder: player, server, entity, or object. Choose the holder from the state lifetime, not convenience.

For every long-lived feature, define:

| Transition | Required action |
|---|---|
| start | reject/replace duplicate session; initialize neutral state; record owner |
| update | validate level/value; update only changed state |
| stop | cancel queue/task; clear client/server state; delete temporary objects |
| death | stop or deliberately restore after respawn |
| quit | stop server work and record whether reconnect restores |
| reconnect | rebuild only from authoritative persisted state |
| reload | cancel old queues/tasks, re-register once, reconcile persisted sessions |
| failure | run idempotent cleanup; leave neutral client behavior |

A loop must have a bounded condition, wait, owner, and cleanup. A flag that outlives its queue needs an expiry or explicit delete path.

## DenizenM-to-client bridge

DenizenM cannot make resource-pack-only code read arbitrary server variables. Pick an actual transport: a native command, a supported packet/API, a marked render carrier, or another evidenced client runtime. Document serialization, update rate, viewer scope, neutral missing state, and reconnect/reload behavior.

For any DenizenM-to-client bridge, server-side command success proves only server-side command success. The client may not have the resource, may reject its shader, or may render differently. Cleanup handlers must cover quit, death policy, kick, resource-pack rejection if observable, and script reload. On reconnect, either restore from authoritative state or remain stopped; never leave that ambiguous.

## Static review checklist

Run `dcore lint` on the complete project, not only one pasted task. Review terminal commands with following siblings, unreachable branches, dynamic injections, queue call graph, loop wait/bounds, broad events, flag lifetime, deprecated target-specific tags/mechanisms, and addon/JAR proof boundaries. End with a separate runtime scenario list.

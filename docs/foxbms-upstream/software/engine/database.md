# Database Module

**Source**: [docs.foxbms.org — Database](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/engine/database/database.html)
**Files**: `src/app/engine/database/database.c`, `database.h`, `database_cfg.c`, `database_cfg.h`

---

## Architecture

Producer/consumer pattern for asynchronous communication between tasks:
- Data produced by a **single producer** → stored in database → consumed by **multiple consumers**
- Data integrity ensured by the module

**Critical constraint**: "Every data entry in the Data-Exchange Module is only written by a single data producer."

## How It Works (Production)

1. Producer calls `DATA_WRITE_DATA()` → message sent to `ftsk_databaseQueue`
2. Engine task dequeues → calls `DATA_IterateOverDatabaseEntries()` → copies data to database
3. Consumer calls `DATA_READ_DATA()` → gets latest copy

## POSIX Port Difference

In cooperative mode, `DATA_IterateOverDatabaseEntries()` is called directly (synchronously) inside `OS_SendToBackOfQueue()` stub. No FreeRTOS queue is involved.

**GAP-ANALYSIS GA-03**: Write and read happen in the same task context. Subtle ordering differences possible vs production where writes and reads are in different task contexts with queue buffering.

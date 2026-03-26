with open("src/app/engine/database/database.c") as f:
    code = f.read()

# Make DATA_IterateOverDatabaseEntries non-static on POSIX
old = 'static void DATA_IterateOverDatabaseEntries(const DATA_QUEUE_MESSAGE_s *kpReceiveMessage);'
new = '''#ifdef FOXBMS_POSIX
void DATA_IterateOverDatabaseEntries(const DATA_QUEUE_MESSAGE_s *kpReceiveMessage);
#else
static void DATA_IterateOverDatabaseEntries(const DATA_QUEUE_MESSAGE_s *kpReceiveMessage);
#endif'''

if old in code:
    code = code.replace(old, new, 1)

old2 = 'static void DATA_IterateOverDatabaseEntries(const DATA_QUEUE_MESSAGE_s *kpReceiveMessage) {'
new2 = '''#ifndef FOXBMS_POSIX
static
#endif
void DATA_IterateOverDatabaseEntries(const DATA_QUEUE_MESSAGE_s *kpReceiveMessage) {'''

if old2 in code:
    code = code.replace(old2, new2, 1)

with open("src/app/engine/database/database.c", "w") as f:
    f.write(code)
print("patched database.c — DATA_IterateOverDatabaseEntries now extern on POSIX")

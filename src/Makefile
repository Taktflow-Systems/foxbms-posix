# foxBMS 2 POSIX vECU Build
# Usage: make -j4

CC = gcc
CFLAGS = -std=c11 -D_GNU_SOURCE -DFOXBMS_POSIX -DGNU_COMPILER -DFOXBMS_USES_FREERTOS=1
CFLAGS += -Wno-unused-parameter -Wno-attributes -Wno-enum-conversion
CFLAGS += -Wno-address-of-packed-member -Wno-missing-braces -Wno-cpp
CFLAGS += -Wno-unterminated-string-initialization -Wno-absolute-value
CFLAGS += -fcommon -g -O0 -include posix_overrides.h

# ROOT points to the foxbms-2 submodule containing upstream foxBMS source
ROOT = ../foxbms-2
BUILD = build

# Include paths: POSIX src dir + FreeRTOS POSIX port + HALCoGen headers + ALL app dirs
INC  = -I.
INC += -I$(ROOT)/src/os/freertos/freertos/include
INC += -I$(ROOT)/src/os/freertos/freertos/portable/ThirdParty/GCC/Posix
INC += -I$(ROOT)/build/app_host_unit_test/include
INC += $(shell find $(ROOT)/src/app $(ROOT)/src/opt $(ROOT)/src/version -type d 2>/dev/null | sed 's/^/-I /')

# FreeRTOS kernel — NOT USED in cooperative mode
# All OS functions stubbed in hal_stubs_posix.c
FREERTOS_SRCS =

# foxBMS application sources (exclude ARM-specific, AFE vendor, bootloader)
APP_SRCS = $(shell find $(ROOT)/src/app -name '*.c' \
    ! -path '*/adi/*' ! -path '*/nxp/*' ! -path '*/maxim/*' ! -path '*/ltc/*' \
    ! -path '*/ti/*' ! -path '*/portable/*' \
    ! -path '*/bender/*' ! -path '*/debug/default/*' \
    ! -path '*/no-imd/*' \
    ! -path '*/bal/history/*' ! -path '*/bal/none/*' \
    ! -path '*/soc/debug/*' ! -path '*/soc/none/*' \
    ! -path '*/soe/debug/*' ! -path '*/soe/none/*' \
    ! -path '*/soh/debug/*' \
    ! -path '*/sof/none/*' \
    ! -path '*/ethernet/*' \
    ! -path '*/ts/tdk/*' ! -path '*/ts/murata/*' ! -path '*/ts/semitec/*' \
    ! -path '*/ts/fake/*' ! -path '*/ts/vishay/*' ! -path '*/epcos/b57861*' \
    ! -path '*/polynomial/*' \
    ! -name 'main.c' ! -name 'fstartup.c' ! -name 'io.c' ! -name 'crc.c' ! -name 'sps.c' ! -name 'sps_cfg.c' \
    ! -name 'os_freertos.c' ! -name 'ftask_freertos.c' \
    ! -name 'spi.c' ! -name 'spi_cfg.c' ! -name 'dma.c' ! -name 'i2c.c' \
    ! -name 'fram.c' ! -name 'pex.c' ! -name 'pex_cfg.c' \
    ! -name 'htsensor.c' ! -name 'nxpfs85xx.c' ! -name 'fs8x_driver*' \
    ! -path '*/sbc/*' ! -name 'diag.c' ! -name 'fassert.c' \
    2>/dev/null)

# foxBMS OS wrapper — exclude os_freertos.c (we provide our own OS stubs)
OS_SRCS = $(ROOT)/src/app/task/os/os.c

# Version
VERSION_SRCS = $(shell find $(ROOT)/src/opt -name '*.c' 2>/dev/null)

# POSIX stubs
POSIX_SRCS = hal_stubs_posix.c

# All sources
ALL_SRCS = foxbms_posix_main.c $(POSIX_SRCS) $(FREERTOS_SRCS) $(APP_SRCS) $(OS_SRCS) $(VERSION_SRCS)

# Object files
ALL_OBJS = $(patsubst %.c,$(BUILD)/%.o,$(notdir $(ALL_SRCS)))

# Deduplicate (some files may appear twice)
OBJS = $(sort $(ALL_OBJS))

TARGET = foxbms-vecu

.PHONY: all clean check

all: $(TARGET)
	@echo "=== Built $(TARGET) ==="

# Create VPATH from all source directories
VPATH = $(sort $(dir $(ALL_SRCS)))

$(BUILD)/%.o: %.c | $(BUILD)
	@echo "CC $<"
	@$(CC) $(CFLAGS) $(INC) -c $< -o $@

$(TARGET): $(OBJS)
	@echo "LINK $@"
	@$(CC) -no-pie $(OBJS) -lpthread -lrt -lm -o $@

$(BUILD):
	mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD) $(TARGET)

# Quick check: compile just the main and stubs
check:
	@echo "Checking foxbms_posix_main.c..."
	@$(CC) $(CFLAGS) $(INC) -c foxbms_posix_main.c -o /dev/null
	@echo "Checking hal_stubs_posix.c..."
	@$(CC) $(CFLAGS) $(INC) -c hal_stubs_posix.c -o /dev/null
	@echo "OK"

# GA-13: Smoke test — start plant model + vECU, check BMS reaches NORMAL
test: $(TARGET)
	@echo "=== Running smoke test ==="
	@python3 test_smoke.py

# List all source files (for debugging)
list:
	@echo "=== APP_SRCS ===" && echo "$(APP_SRCS)" | tr ' ' '\n' | wc -l
	@echo "=== FREERTOS_SRCS ===" && echo "$(FREERTOS_SRCS)" | tr ' ' '\n' | wc -l
	@echo "=== Total ===" && echo "$(ALL_SRCS)" | tr ' ' '\n' | wc -l

/**
 * @file    foxbms_posix_main.c
 * @brief   foxBMS POSIX vECU — cooperative main loop replacing FreeRTOS scheduler
 * @date    2026-03-20
 *
 * Replaces foxBMS main.c. Calls the same init functions but runs
 * cyclic tasks in a simple while loop instead of FreeRTOS scheduler.
 */

#define _GNU_SOURCE
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>

/* foxBMS init functions (from main.c) */
extern void muxInit(void);
extern void gioInit(void);
extern void adcInit(void);
extern void hetInit(void);
extern void etpwmInit(void);
extern void crcInit(void);
extern void canInit(void);
extern uint32_t getResetSource(void);
extern void _enable_IRQ_interrupt_(void);

/* foxBMS application init */
extern void MINFO_SetResetSource(uint32_t src);
extern void SPI_Initialize(void);
extern void I2C_Initialize(void);
extern void DMA_Initialize(void);
extern void PWM_Initialize(void);
extern void LED_SetDebugLed(void);
extern uint32_t DIAG_Initialize(void *diag_dev);
extern void MATH_StartupSelfTest(void);
extern uint32_t OS_CheckTimeHasPassedSelfTest(void);

/* No FreeRTOS — cooperative mode */

/* foxBMS boot state */
extern volatile uint8_t os_boot;
extern volatile bool ftsk_allQueuesCreated;  /* defined in hal_stubs_posix.c */

/* foxBMS task init functions */
extern void FTSK_InitializeUserCodeEngine(void);
extern void FTSK_InitializeUserCodePreCyclicTasks(void);

/* foxBMS cyclic functions */
extern void FTSK_RunUserCodeEngine(void);
extern void FTSK_RunUserCodeCyclic1ms(void);
extern void FTSK_RunUserCodeCyclic10ms(void);
extern void FTSK_RunUserCodeCyclic100ms(void);
extern void FTSK_RunUserCodeCyclicAlgorithm100ms(void);

/* diag_device from diag_cfg.c — opaque pointer to avoid including diag headers */
extern char diag_device[];  /* actually DIAG_DEV_s, but we just pass the address */

/* os_boot states */
#define OS_OFF (0u)
#define OS_SCHEDULER_RUNNING (4u)
#define OS_ENGINE_RUNNING (5u)
#define OS_PRE_CYCLIC_INIT_DONE (6u)

/* SocketCAN */
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <fcntl.h>

static int can_socket = -1;

int posix_can_open(const char *ifname)
{
    if (can_socket >= 0) {
        /* Already open — idempotent, skip re-open */
        return 0;
    }
    struct sockaddr_can addr;
    struct ifreq ifr;
    can_socket = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (can_socket < 0) { perror("socket"); return -1; }
    fcntl(can_socket, F_SETFL, O_NONBLOCK);
    strncpy(ifr.ifr_name, ifname, IFNAMSIZ - 1);
    ifr.ifr_name[IFNAMSIZ - 1] = '\0';
    if (ioctl(can_socket, SIOCGIFINDEX, &ifr) < 0) { perror("ioctl"); close(can_socket); can_socket = -1; return -1; }
    memset(&addr, 0, sizeof(addr));
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;
    if (bind(can_socket, (struct sockaddr *)&addr, sizeof(addr)) < 0) { perror("bind"); close(can_socket); can_socket = -1; return -1; }
    fprintf(stderr, "[CAN] '%s' opened (fd=%d)\n", ifname, can_socket);
    return 0;
}

int posix_can_send(uint32_t id, const uint8_t *data, uint8_t dlc)
{
    if (can_socket < 0) return -1;
    struct can_frame frame;
    memset(&frame, 0, sizeof(frame));
    frame.can_id = id;
    frame.can_dlc = dlc > 8 ? 8 : dlc;
    memcpy(frame.data, data, frame.can_dlc);
    ssize_t n = write(can_socket, &frame, sizeof(frame));
    return (n == sizeof(frame)) ? 0 : -1;
}

/* Timing */
static uint64_t get_time_us(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000ULL + (uint64_t)ts.tv_nsec / 1000ULL;
}

/* CAN RX from SocketCAN — feed into foxBMS CAN RX buffer queue */
extern void posix_can_rx_inject(uint32_t id, uint8_t *data, uint8_t dlc);

static volatile int running = 1;
static void sigint_handler(int sig) { (void)sig; running = 0; }

int main(int argc, char *argv[])
{
    signal(SIGINT, sigint_handler);
    setbuf(stdout, NULL);
    setbuf(stderr, NULL);

    /* Parse --timeout N (seconds, 0 = run forever) */
    int timeout_s = 0;
    for (int i = 1; i < argc - 1; i++) {
        if (strcmp(argv[i], "--timeout") == 0) {
            timeout_s = atoi(argv[i + 1]);
            break;
        }
    }

    /* Open SocketCAN early */
    const char *can_if = getenv("FOXBMS_CAN_IF");
    if (!can_if) can_if = "vcan1";
    fprintf(stderr, "=== foxBMS 2 POSIX vECU ===\n");
    if (timeout_s > 0) {
        fprintf(stderr, "[init] Timeout: %d s\n", timeout_s);
    }
    posix_can_open(can_if);

    /* Phase 1: Hardware init (all stubbed) */
    fprintf(stderr, "[init] HAL init...\n");
    MINFO_SetResetSource(getResetSource());
    muxInit();
    gioInit();
    SPI_Initialize();
    adcInit();
    hetInit();
    etpwmInit();
    crcInit();
    LED_SetDebugLed();
    I2C_Initialize();
    DMA_Initialize();
    PWM_Initialize();
    fprintf(stderr, "[init] HAL done\n");

    /* Phase 2: DIAG init */
    fprintf(stderr, "[init] DIAG...\n");
    DIAG_Initialize(&diag_device);
    MATH_StartupSelfTest();
    OS_CheckTimeHasPassedSelfTest();
    fprintf(stderr, "[init] DIAG done\n");

    /* Phase 3: No FreeRTOS — just set the flag so DATA_Initialize passes */
    fprintf(stderr, "[init] Setting queue flag...\n");
    ftsk_allQueuesCreated = true;
    fprintf(stderr, "[init] Ready for app init\n");

    /* Phase 4: Run engine init (normally in engine task) */
    fprintf(stderr, "[init] Engine init...\n");
    os_boot = OS_SCHEDULER_RUNNING;
    FTSK_InitializeUserCodeEngine();
    os_boot = OS_ENGINE_RUNNING;
    fprintf(stderr, "[init] Engine done\n");

    /* Phase 5: Run pre-cyclic init (normally in 1ms task) */
    fprintf(stderr, "[init] PreCyclic init...\n");
    FTSK_InitializeUserCodePreCyclicTasks();
    os_boot = OS_PRE_CYCLIC_INIT_DONE;
    fprintf(stderr, "[init] PreCyclic done\n");

    /* Phase 6: Main loop — call cyclic functions with timing */
    fprintf(stderr, "[run] Entering main loop\n");

    uint64_t last_1ms = get_time_us();
    uint64_t last_10ms = last_1ms;
    uint64_t last_100ms = last_1ms;
    uint64_t start_us = last_1ms;
    uint32_t tick = 0;

    /* GA-01: Cycle time measurement */
    uint64_t max_1ms_us = 0, max_10ms_us = 0, max_100ms_us = 0;
    uint32_t deadline_violations = 0;

    while (running) {
        uint64_t now = get_time_us();

        /* GA-28: Check timeout */
        if (timeout_s > 0 && (now - start_us) >= (uint64_t)timeout_s * 1000000ULL) {
            fprintf(stderr, "[run] Timeout (%d s) elapsed — stopping\n", timeout_s);
            running = 0;
            break;
        }

        /* CAN RX from SocketCAN — read all pending frames */
        {
            struct can_frame rx_frame;
            while (read(can_socket, &rx_frame, sizeof(rx_frame)) == sizeof(rx_frame)) {
                /* Skip error frames, RTR frames, and extended (29-bit) frames —
                 * foxBMS uses standard 11-bit IDs only. */
                if (rx_frame.can_id & (CAN_ERR_FLAG | CAN_RTR_FLAG | CAN_EFF_FLAG)) {
                    continue;
                }
                posix_can_rx_inject(rx_frame.can_id & CAN_SFF_MASK, rx_frame.data, rx_frame.can_dlc);
            }
        }

        /* 1ms cyclic */
        if (now - last_1ms >= 1000) {
            uint64_t t0 = get_time_us();
            last_1ms += 1000;
            if (now - last_1ms >= 2000) { last_1ms = now; } /* catch-up guard */
            FTSK_RunUserCodeCyclic1ms();
            FTSK_RunUserCodeEngine();
            /* MEAS_Control() runs at 1ms rate — gated here rather than every loop
             * iteration (which was 500µs) to match the AFE task period in FreeRTOS. */
            {
                extern void MEAS_Control(void);
                MEAS_Control();
            }
            uint64_t dt = get_time_us() - t0;
            if (dt > max_1ms_us) max_1ms_us = dt;
            if (dt > 1000) { /* exceeded 1ms deadline */
                deadline_violations++;
                if (deadline_violations <= 10) {
                    fprintf(stderr, "[TIMING] 1ms task took %luus (deadline 1000us)\n", (unsigned long)dt);
                }
            }
            tick++;
        }

        /* 10ms cyclic */
        if (now - last_10ms >= 10000) {
            uint64_t t0 = get_time_us();
            last_10ms += 10000;
            if (now - last_10ms >= 20000) { last_10ms = now; } /* catch-up guard */
            FTSK_RunUserCodeCyclic10ms();
            uint64_t dt = get_time_us() - t0;
            if (dt > max_10ms_us) max_10ms_us = dt;
            if (dt > 10000) {
                deadline_violations++;
                if (deadline_violations <= 10) {
                    fprintf(stderr, "[TIMING] 10ms task took %luus (deadline 10000us)\n", (unsigned long)dt);
                }
            }
        }

        /* 100ms cyclic */
        if (now - last_100ms >= 100000) {
            uint64_t t0 = get_time_us();
            last_100ms += 100000;
            if (now - last_100ms >= 200000) { last_100ms = now; } /* catch-up guard */
            FTSK_RunUserCodeCyclic100ms();
            FTSK_RunUserCodeCyclicAlgorithm100ms();
            uint64_t dt = get_time_us() - t0;
            if (dt > max_100ms_us) max_100ms_us = dt;
            if (dt > 100000) {
                deadline_violations++;
                if (deadline_violations <= 10) {
                    fprintf(stderr, "[TIMING] 100ms task took %luus (deadline 100000us)\n", (unsigned long)dt);
                }
            }
        }

        /* Status every 5 seconds */
        if (tick > 0 && tick % 5000 == 0) {
            fprintf(stderr, "[%u] foxBMS running\n", tick / 1000);
        }

        /* Sleep 500us to avoid busy-wait */
        usleep(500);
    }

    /* GA-22: Graceful shutdown — open all contactors */
    fprintf(stderr, "[exit] Graceful shutdown — opening all contactors...\n");
    {
        extern void SPS_SwitchOffAllGeneralIoChannels(void);
        SPS_SwitchOffAllGeneralIoChannels();
    }

    /* GA-01: Print timing summary */
    fprintf(stderr, "[exit] foxBMS stopped after %u ticks\n", tick);
    fprintf(stderr, "[TIMING] Max execution times: 1ms=%luus, 10ms=%luus, 100ms=%luus\n",
            (unsigned long)max_1ms_us, (unsigned long)max_10ms_us, (unsigned long)max_100ms_us);
    fprintf(stderr, "[TIMING] Deadline violations: %u\n", deadline_violations);
    return 0;
}

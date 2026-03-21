/**
 * @file    hal_stubs_posix.c
 * @brief   POSIX stubs for all HALCoGen and hardware-dependent functions
 * @date    2026-03-20
 *
 * Provides no-op implementations for all TMS570 HAL functions so foxBMS
 * application code can compile and run on Linux x86_64.
 */

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sil_layer.h"

/* ================================================================
 * SIL probe state variables — populated by stubs, read by probes
 * ================================================================ */
#ifdef FOXBMS_SIL_PROBES
uint8_t  posix_sil_bms_state = 0u;
uint8_t  posix_sil_bms_substate = 0u;
float    posix_sil_soc_pct = 50.0f;
uint16_t posix_sil_cell_v_min = 3700u;
uint16_t posix_sil_cell_v_max = 3700u;
int32_t  posix_sil_string_voltage_mv = 66600;
int32_t  posix_sil_bus_voltage_mv = 66600;
int16_t  posix_sil_cell_t_min = 250;
int16_t  posix_sil_cell_t_max = 250;
int32_t  posix_sil_current_ma = 0;
uint32_t posix_sil_db_write_count = 0u;
uint32_t posix_sil_db_read_count = 0u;
#endif

/* Prevent HALCoGen type conflicts */
typedef uint32_t uint32;
typedef uint16_t uint16;
typedef uint8_t uint8;
typedef int32_t sint32;
typedef int16_t sint16;
typedef int8_t sint8;
typedef _Bool boolean;
#define TRUE  (1)
#define FALSE (0)
#define NULL_PTR ((void *)0)

/* ================================================================
 * HALCoGen Initialization Functions (all no-op)
 * ================================================================ */

/* CAN message box ID tracking for POSIX SocketCAN */
#define CAN_MAX_MAILBOXES 64u
static uint32_t can_mailbox_id[CAN_MAX_MAILBOXES] = {0};

/* SocketCAN integration */
extern int posix_can_open(const char *ifname);

/* Constructor: runs before main() */
__attribute__((constructor)) void posix_early_init(void) {
    fprintf(stderr, "[POSIX] Binary started. Entering main()...\n");
    fflush(stderr);
    /* Open SocketCAN early so CAN TX works before canInit() */
    const char *can_if = getenv("FOXBMS_CAN_IF");
    if (!can_if) can_if = "vcan1";
    posix_can_open(can_if);
}

/* Force SBC state to RUNNING after main() init but before tasks check it.
 * Called from a POSIX-specific hook. We use a byte offset approach since
 * we can't include sbc.h (type conflicts). */
void posix_force_sbc_running(void);  /* called from patched ftask_cfg.c */

void muxInit(void) {
    fprintf(stderr, "[POSIX] muxInit()\n");
    fflush(stderr);
}
void gioInit(void) { fprintf(stderr, "[POSIX] gioInit()\n"); fflush(stderr); }
void adcInit(void) { fprintf(stderr, "[POSIX] adcInit()\n"); fflush(stderr); }
void hetInit(void) { fprintf(stderr, "[POSIX] hetInit()\n"); fflush(stderr); }
void etpwmInit(void) { fprintf(stderr, "[POSIX] etpwmInit()\n"); fflush(stderr); }
void crcInit(void) { fprintf(stderr, "[POSIX] crcInit()\n"); fflush(stderr); }
void spiInit(void) { fprintf(stderr, "[POSIX] spiInit()\n"); fflush(stderr); }
/* SocketCAN integration */
extern int posix_can_open(const char *ifname);
extern int posix_can_send(uint32_t id, const uint8_t *data, uint8_t dlc);

static int can_initialized_posix = 0;
void canInit(void) {
    const char *can_if = getenv("FOXBMS_CAN_IF");
    if (!can_if) can_if = "vcan1";
    int ret = posix_can_open(can_if);
    can_initialized_posix = (ret == 0) ? 1 : 0;
    fprintf(stderr, "[POSIX] canInit() → SocketCAN '%s' ret=%d\n", can_if, ret);
    fflush(stderr);
}
void i2cInit(void) {}
void systemInit(void) {}

/* ================================================================
 * CAN HAL — replaced by SocketCAN in foxbms_posix_main.c
 * These are called by foxBMS CAN driver (can.c)
 * ================================================================ */

/* canTransmit routes to SocketCAN */
extern int posix_can_send(uint32_t id, const uint8_t *data, uint8_t dlc);

static uint32_t can_tx_count = 0u;

/* SIL probe: capture last TX data for key CAN IDs */
#ifdef FOXBMS_SIL_PROBES
uint8_t posix_last_can_tx_220[8] = {0};
#endif

uint32_t canTransmit(void *node, uint32_t messageBox, const uint8_t *data)
{
    (void)node;
    uint32_t id = 0u;
    if (messageBox > 0u && messageBox <= CAN_MAX_MAILBOXES) {
        id = can_mailbox_id[messageBox - 1u];
    }

#ifdef FOXBMS_SIL_PROBES
    /* Capture TX data for probe snooping */
    if (id == 0x220u && data != NULL) {
        memcpy(posix_last_can_tx_220, data, 8u);
    }
    /* Update SIL state from CAN TX */
    if (id == 0x521u && data != NULL && !sil_override_active(SIL_PACK_CURRENT, 0)) {
        /* IVT current: bytes 2-5 big-endian — only update if not overridden */
        int32_t cur;
        uint8_t tmp[4] = {data[5], data[4], data[3], data[2]};  /* swap to LE */
        memcpy(&cur, tmp, 4);
        posix_sil_current_ma = cur;
    }
#endif

    /* DLC hardcoded to 8 — see comment in plan */
    int ret = posix_can_send(id, data, 8u);
    can_tx_count++;
    if (can_tx_count <= 5u) {
        fprintf(stderr, "[POSIX] canTransmit mb=%u id=0x%03X ret=%d\n",
                (unsigned)messageBox, (unsigned)id, ret);
        fflush(stderr);
    }
    return 1u;
}

uint32_t canGetData(void *node, uint32_t messageBox, uint8_t *const data)
{
    (void)node;
    (void)messageBox;
    (void)data;
    return 0u; /* no new data */
}

uint32_t canIsTxMessagePending(void *node, uint32_t messageBox)
{
    (void)node;
    (void)messageBox;
    return 0u; /* not pending */
}

/* ================================================================
 * ADC
 * ================================================================ */

void adcStartConversion(void *adc, uint32_t group)
{
    (void)adc;
    (void)group;
}

uint32_t adcIsConversionComplete(void *adc, uint32_t group)
{
    (void)adc;
    (void)group;
    return 1u; /* always complete */
}

uint32_t adcGetData(void *adc, uint32_t group, void *data)
{
    (void)adc;
    (void)group;
    (void)data;
    return 0u;
}

/* ================================================================
 * SPI
 * ================================================================ */

uint32_t spiTransmitData(void *node, void *config, uint32_t len, uint16_t *data)
{
    (void)node;
    (void)config;
    (void)len;
    (void)data;
    return 0u; /* success */
}

/* ================================================================
 * I2C
 * ================================================================ */

void i2cSetSlaveAdd(void *i2c, uint32_t addr)
{
    (void)i2c;
    (void)addr;
}

void i2cSetDirection(void *i2c, uint32_t dir)
{
    (void)i2c;
    (void)dir;
}

void i2cSetCount(void *i2c, uint32_t count)
{
    (void)i2c;
    (void)count;
}

void i2cSetMode(void *i2c, uint32_t mode)
{
    (void)i2c;
    (void)mode;
}

void i2cSetStop(void *i2c)
{
    (void)i2c;
}

void i2cSetStart(void *i2c)
{
    (void)i2c;
}

void i2cSendByte(void *i2c, uint8_t data)
{
    (void)i2c;
    (void)data;
}

uint8_t i2cReceiveByte(void *i2c)
{
    (void)i2c;
    return 0u;
}

uint32_t i2cIsStopDetected(void *i2c)
{
    (void)i2c;
    return 1u; /* always detected */
}

/* ================================================================
 * GIO (GPIO)
 * ================================================================ */

void gioSetBit(void *port, uint32_t bit, uint32_t value)
{
    (void)port;
    (void)bit;
    (void)value;
}

uint32_t gioGetBit(void *port, uint32_t bit)
{
    (void)port;
    (void)bit;
    return 0u;
}

void gioSetDirection(void *port, uint32_t bit, uint32_t direction)
{
    (void)port;
    (void)bit;
    (void)direction;
}

/* ================================================================
 * MDIO / Ethernet PHY
 * ================================================================ */

void MDIOInit(uint32_t base, uint32_t freqIn, uint32_t freqOut)
{
    (void)base;
    (void)freqIn;
    (void)freqOut;
}

/* ================================================================
 * CPU / Interrupt
 * ================================================================ */

void _enable_IRQ_interrupt_(void) { fprintf(stderr, "[POSIX] _enable_IRQ_interrupt_()\n"); fflush(stderr); }
void _disable_IRQ_interrupt_(void) {}

/* ================================================================
 * OS Wrapper (replaces os_freertos.c — no FreeRTOS scheduler)
 * ================================================================ */

#include <unistd.h>
#include <time.h>
#include <pthread.h>

static pthread_mutex_t os_mutex = PTHREAD_MUTEX_INITIALIZER;

void OS_InitializeScheduler(void) {}
void OS_StartScheduler(void) { /* never called in POSIX cooperative mode */ }

void OS_EnterTaskCritical(void) { pthread_mutex_lock(&os_mutex); }
void OS_ExitTaskCritical(void) { pthread_mutex_unlock(&os_mutex); }

/* OS_IncrementTimer defined in os.c */

uint32_t OS_GetTickCount(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)((ts.tv_sec * 1000u) + (ts.tv_nsec / 1000000u));
}

void OS_DelayTask(uint32_t ms) { usleep(ms * 1000u); }

void OS_DelayTaskUntil(uint32_t *pPrevWakeTime, uint32_t ms) {
    (void)pPrevWakeTime;
    usleep(ms * 1000u);
}

void OS_MarkTaskAsRequiringFpuContext(void) {}

/* Notification stubs — not used in cooperative mode */
typedef enum { OS_SUCCESS = 0, OS_FAIL = 1 } OS_STD_RETURN_e;

OS_STD_RETURN_e OS_WaitForNotification(uint32_t *pVal, uint32_t timeout) {
    (void)pVal; (void)timeout; return OS_FAIL;
}
OS_STD_RETURN_e OS_NotifyFromIsr(void *task, uint32_t val) {
    (void)task; (void)val; return OS_SUCCESS;
}
OS_STD_RETURN_e OS_WaitForNotificationIndexed(uint32_t idx, uint32_t clear, uint32_t *pVal, uint32_t timeout) {
    (void)idx; (void)clear; (void)pVal; (void)timeout; return OS_FAIL;
}
OS_STD_RETURN_e OS_NotifyIndexedFromIsr(void *task, uint32_t idx, uint32_t val, uint32_t action, void *pHigher) {
    (void)task; (void)idx; (void)val; (void)action; (void)pHigher; return OS_SUCCESS;
}
OS_STD_RETURN_e OS_ClearNotificationIndexed(uint32_t idx) { (void)idx; return OS_SUCCESS; }

/* ================================================================
 * CAN RX Ring Buffer for POSIX SocketCAN → foxBMS
 * ================================================================ */
typedef struct {
    void *canNode;
    uint32_t id;
    uint32_t idType; /* 0 = standard */
    uint8_t data[8];
} POSIX_CAN_RX_ELEMENT_s;

#define POSIX_CAN_RX_BUF_SIZE 64
static POSIX_CAN_RX_ELEMENT_s posix_can_rx_buf[POSIX_CAN_RX_BUF_SIZE];
static volatile uint32_t posix_can_rx_head = 0;
static volatile uint32_t posix_can_rx_tail = 0;

/* CAN_NODE_1 defined in can_cfg.c */
extern const char can_node1[];
#define CAN_NODE_1_PTR ((void *)&can_node1)

static uint32_t posix_can_rx_overflow_count = 0u;

void posix_can_rx_inject(uint32_t id, uint8_t *data, uint8_t dlc) {
    uint32_t next = (posix_can_rx_head + 1) % POSIX_CAN_RX_BUF_SIZE;
    if (next == posix_can_rx_tail) {
        posix_can_rx_overflow_count++;
        if (posix_can_rx_overflow_count == 1u) {
            fprintf(stderr, "[CAN-RX] WARNING: RX ring buffer full — dropping frame id=0x%03X "
                    "(buffer size=%d). Further overflows will be counted but not logged.\n",
                    (unsigned)id, POSIX_CAN_RX_BUF_SIZE);
            fflush(stderr);
        }
        return;
    }
    posix_can_rx_buf[posix_can_rx_head].canNode = CAN_NODE_1_PTR;
    posix_can_rx_buf[posix_can_rx_head].id = id;
    posix_can_rx_buf[posix_can_rx_head].idType = 0; /* standard */
    memset(posix_can_rx_buf[posix_can_rx_head].data, 0, 8);
    if (dlc > 8) dlc = 8;
    memcpy(posix_can_rx_buf[posix_can_rx_head].data, data, dlc);
    posix_can_rx_head = next;
}

/* Database: direct call instead of queue — DATA_IterateOverDatabaseEntries made extern */
extern void DATA_IterateOverDatabaseEntries(const void *kpReceiveMessage);

/* Forward declarations for AFE queue buffers (defined later with queue handles) */
#define POSIX_AFE_QUEUE_SIZE 16
static uint8_t posix_afe_volt_buf[POSIX_AFE_QUEUE_SIZE][64];
static volatile uint32_t posix_afe_volt_head, posix_afe_volt_tail;
static uint8_t posix_afe_temp_buf[POSIX_AFE_QUEUE_SIZE][64];
static volatile uint32_t posix_afe_temp_head, posix_afe_temp_tail;

/* Queue operations — CAN RX queue + database queue from ring buffers */
OS_STD_RETURN_e OS_ReceiveFromQueue(void *xQueue, void *pvBuffer, uint32_t ticksToWait) {
    (void)ticksToWait;
    /* Only CAN RX queue has data */
    extern void *ftsk_canRxQueue;
    /* AFE cell voltage queue (defined later in this file) */
    extern void *ftsk_canToAfeCellVoltagesQueue;
    extern void *ftsk_canToAfeCellTemperaturesQueue;
    if (xQueue == ftsk_canToAfeCellVoltagesQueue && posix_afe_volt_head != posix_afe_volt_tail) {
        memcpy(pvBuffer, posix_afe_volt_buf[posix_afe_volt_tail], 16);
        posix_afe_volt_tail = (posix_afe_volt_tail + 1) % POSIX_AFE_QUEUE_SIZE;
#ifdef FOXBMS_SIL_PROBES
        posix_sil_db_read_count++;
#endif
        return OS_SUCCESS;
    }
    /* AFE cell temperature queue */
    if (xQueue == ftsk_canToAfeCellTemperaturesQueue && posix_afe_temp_head != posix_afe_temp_tail) {
        memcpy(pvBuffer, posix_afe_temp_buf[posix_afe_temp_tail], 16);
        posix_afe_temp_tail = (posix_afe_temp_tail + 1) % POSIX_AFE_QUEUE_SIZE;
#ifdef FOXBMS_SIL_PROBES
        posix_sil_db_read_count++;
#endif
        return OS_SUCCESS;
    }
    /* CAN RX queue */
    if (xQueue == ftsk_canRxQueue && posix_can_rx_head != posix_can_rx_tail) {
        memcpy(pvBuffer, &posix_can_rx_buf[posix_can_rx_tail], sizeof(POSIX_CAN_RX_ELEMENT_s));
        posix_can_rx_tail = (posix_can_rx_tail + 1) % POSIX_CAN_RX_BUF_SIZE;
        { static uint32_t rx_cnt = 0; rx_cnt++;
          if (rx_cnt <= 20 || posix_can_rx_buf[(posix_can_rx_tail - 1 + POSIX_CAN_RX_BUF_SIZE) % POSIX_CAN_RX_BUF_SIZE].id == 0x210) { fprintf(stderr, "[CAN-RX] Dequeued id=0x%03X (#%u)" "\n",
              posix_can_rx_buf[(posix_can_rx_tail - 1 + POSIX_CAN_RX_BUF_SIZE) % POSIX_CAN_RX_BUF_SIZE].id, rx_cnt);
              fflush(stderr); }
        }
        return OS_SUCCESS;
    }
    return OS_FAIL;
}
OS_STD_RETURN_e OS_SendToBackOfQueue(void *xQueue, const void *pvItem, uint32_t ticksToWait) {
    (void)ticksToWait;
    extern void *ftsk_databaseQueue;
    if (xQueue == ftsk_databaseQueue && pvItem != NULL) {
        DATA_IterateOverDatabaseEntries(pvItem);
#ifdef FOXBMS_SIL_PROBES
        posix_sil_db_write_count++;
#endif
    }
    /* AFE cell voltage queue */
    extern void *ftsk_canToAfeCellVoltagesQueue;
    extern void *ftsk_canToAfeCellTemperaturesQueue;
    if (xQueue == ftsk_canToAfeCellVoltagesQueue && pvItem != NULL) {
        uint32_t next = (posix_afe_volt_head + 1) % POSIX_AFE_QUEUE_SIZE;
        if (next != posix_afe_volt_tail) {
            memcpy(posix_afe_volt_buf[posix_afe_volt_head], pvItem, 16);
            posix_afe_volt_head = next;
        }
    }
    /* AFE cell temperature queue */
    if (xQueue == ftsk_canToAfeCellTemperaturesQueue && pvItem != NULL) {
        uint32_t next = (posix_afe_temp_head + 1) % POSIX_AFE_QUEUE_SIZE;
        if (next != posix_afe_temp_tail) {
            memcpy(posix_afe_temp_buf[posix_afe_temp_head], pvItem, 16);
            posix_afe_temp_head = next;
        }
    }
    return OS_SUCCESS;
}
OS_STD_RETURN_e OS_SendToBackOfQueueFromIsr(void *xQueue, const void *pvItem, void *pHigher) {
    (void)xQueue; (void)pvItem; (void)pHigher;
    return OS_SUCCESS;
}
uint32_t OS_GetNumberOfStoredMessagesInQueue(void *xQueue) {
    (void)xQueue;
    return 0u;
}

void OS_SuspendTask(void *task) { (void)task; }
void OS_ResumeTask(void *task) { (void)task; }

/* CheckTimeHasPassed needs OS_GetTickCount which is defined above */
extern uint32_t OS_CheckTimeHasPassedSelfTest(void);  /* defined in os.c, uses OS_GetTickCount */

/* foxBMS queue/task handle stubs (normally in ftask_freertos.c) */
volatile bool ftsk_allQueuesCreated = false;
static uint8_t dummy_dbQueue_storage[1] = {0};
void *ftsk_databaseQueue = dummy_dbQueue_storage; /* non-NULL for queue check */
void *ftsk_imdCanDataQueue = NULL;
static uint8_t dummy_canRxQueue_storage[1] = {0};
void *ftsk_canRxQueue = dummy_canRxQueue_storage; /* non-NULL so queue check passes */
void *ftsk_canTxUnsentMessagesQueue = NULL;
void *ftsk_afeRequestQueue = NULL;
void *ftsk_rtcSetTimeQueue = NULL;
void *ftsk_afeToI2cQueue = NULL;
void *ftsk_afeFromI2cQueue = NULL;
/* AFE cell data queue handles (buffers declared earlier) */
static uint8_t dummy_afe_volt_q[1] = {0};
static uint8_t dummy_afe_temp_q[1] = {0};
void *ftsk_canToAfeCellTemperaturesQueue = dummy_afe_temp_q;
void *ftsk_canToAfeCellVoltagesQueue = dummy_afe_volt_q;
void *ftsk_taskHandleAfe = NULL;
void *ftsk_taskHandleI2c = NULL;

/* FreeRTOS API stubs (no scheduler) */
void FTSK_CreateQueues(void) {}
void FTSK_CreateTasks(void) {}
void vPortYield(void) {}
uint32_t xQueueGenericSend(void *q, const void *item, uint32_t ticks, uint32_t type) {
    (void)q; (void)item; (void)ticks; (void)type; return 1u;
}
uint32_t xTaskGenericNotifyFromISR(void *t, uint32_t i, uint32_t v, uint32_t a, uint32_t *p, void *h) {
    (void)t; (void)i; (void)v; (void)a; (void)p; (void)h; return 1u;
}
uint32_t xTaskGetTickCount(void) { return OS_GetTickCount(); }
void *xTimerCreateStatic(const char *n, uint32_t p, uint32_t r, void *id, void *cb, void *buf) {
    (void)n; (void)p; (void)r; (void)id; (void)cb; (void)buf;
    static uint8_t dummy_timer[64]; return dummy_timer;
}
uint32_t xTimerGenericCommandFromTask(void *t, uint32_t cmd, uint32_t opt, uint32_t *h, uint32_t ticks) {
    (void)t; (void)cmd; (void)opt; (void)h; (void)ticks; return 1u;
}

/* FreeRTOS application hooks — required by kernel */
static uint32_t idle_stack[128];
static uint32_t timer_stack[128];
void vApplicationGetIdleTaskMemory(void **ppTCB, void **ppStack, uint32_t *pSize) {
    static uint8_t tcb[256]; *ppTCB = tcb; *ppStack = idle_stack; *pSize = 128;
}
void vApplicationGetTimerTaskMemory(void **ppTCB, void **ppStack, uint32_t *pSize) {
    static uint8_t tcb[256]; *ppTCB = tcb; *ppStack = timer_stack; *pSize = 128;
}
void vApplicationIdleHook(void) {}
void vApplicationStackOverflowHook(void *task, char *name) { (void)task; (void)name; }

/* xQueueSendToBack wrapper — might be a macro, provide function version */
extern uint32_t xQueueGenericSend(void *, const void *, uint32_t, uint32_t);
uint32_t xQueueSendToBack(void *q, const void *item, uint32_t ticks) {
    return xQueueGenericSend(q, item, ticks, 0);
}
void _cacheEnable_(void) {}
void _cacheDisable_(void) {}

uint32_t getResetSource(void) { fprintf(stderr, "[POSIX] getResetSource()\n"); fflush(stderr); return 0u; }

/* ================================================================
 * LED (printf debug)
 * ================================================================ */

/* LED_SetDebugLed defined in real led.c */

/* ================================================================
 * Checksum / CRC
 * ================================================================ */

/* CHK_ValidateChecksum, MATH_StartupSelfTest defined in real source files */

/* ================================================================
 * Reset source
 * ================================================================ */

/* MINFO_SetResetSource defined in real master_info.c */

/* ================================================================
 * SPI Initialize (foxBMS wrapper)
 * ================================================================ */

/* SPI stubs (spi.c excluded — accesses hardware registers) */
void SPI_Initialize(void) {}
uint32_t SPI_TransmitReceiveData(void *pIf, uint16_t *pTx, uint16_t *pRx, uint32_t len) {
    (void)pIf; (void)pTx; (void)pRx; (void)len; return 0u;
}
uint32_t SPI_TransmitReceiveDataDma(void *pIf, uint16_t *pTx, uint16_t *pRx, uint32_t len) {
    (void)pIf; (void)pTx; (void)pRx; (void)len; return 0u;
}
uint32_t SPI_TransmitData(void *pIf, uint16_t *pTx, uint32_t len) {
    (void)pIf; (void)pTx; (void)len; return 0u;
}
uint32_t SPI_Lock(uint8_t spi) { (void)spi; return 0u; }
void SPI_Unlock(uint8_t spi) { (void)spi; }
uint8_t SPI_GetSpiIndex(void *pNode) { (void)pNode; return 0u; }
void DMA_Initialize(void) {}
void I2C_Initialize(void) {}

/* FRAM stubs (fram.c excluded — uses SPI hardware) */
void FRAM_Initialize(void) { fprintf(stderr, "[POSIX] FRAM_Initialize stubbed\n"); fflush(stderr); }
uint32_t FRAM_ReinitializeAllEntries(void) { return 0u; }
uint32_t FRAM_ReadData(uint32_t blockId) { (void)blockId; return 0u; /* FRAM_ACCESS_OK */ }
uint32_t FRAM_WriteData(uint32_t blockId) { (void)blockId; return 0u; }

/* PEX stubs */
void PEX_Initialize(void) {}
void PEX_Trigger(void) {}
void PEX_SetPin(uint8_t exp, uint8_t port, uint8_t pin) { (void)exp; (void)port; (void)pin; }
void PEX_ResetPin(uint8_t exp, uint8_t port, uint8_t pin) { (void)exp; (void)port; (void)pin; }
uint8_t PEX_GetPin(uint8_t exp, uint8_t port, uint8_t pin) { (void)exp; (void)port; (void)pin; return 0u; }
void PEX_SetPinDirectionOutput(uint8_t exp, uint8_t port, uint8_t pin) { (void)exp; (void)port; (void)pin; }
void PEX_SetPinDirectionInput(uint8_t exp, uint8_t port, uint8_t pin) { (void)exp; (void)port; (void)pin; }

/* HT sensor stub */
void HTSEN_Trigger(void) {}

/* I2C DMA stubs */
uint32_t I2C_WriteDma(void *i2c, uint32_t addr, uint32_t len, uint8_t *data) {
    (void)i2c; (void)addr; (void)len; (void)data; return 0u;
}
uint32_t I2C_ReadDma(void *i2c, uint32_t addr, uint32_t len, uint8_t *data) {
    (void)i2c; (void)addr; (void)len; (void)data; return 0u;
}
uint32_t I2C_WriteReadDma(void *i2c, uint32_t addr, uint32_t wlen, uint8_t *wdata, uint32_t rlen, uint8_t *rdata) {
    (void)i2c; (void)addr; (void)wlen; (void)wdata; (void)rlen; (void)rdata; return 0u;
}

/* ================================================================
 * Phase 3: SIL probe state variables for DIAG
 *
 * These are populated by the patched real diag.c (via patch_diag_probe.py)
 * and read by the SIL probe system. They must NOT be static so the
 * patched DIAG_Handler() in diag.c can reference them via extern.
 * ================================================================ */
#ifdef FOXBMS_SIL_PROBES
uint32_t posix_diag_fault_count = 0u;
uint8_t  posix_diag_last_id = 0u;
uint8_t  posix_diag_last_event = 0u;
uint64_t posix_diag_bitmap = 0u;  /* bit per DIAG ID (up to 64) */
#endif

/* DIAG functions are now provided by the real foxBMS diag.c
 * (included via Makefile, hardware-absent IDs disabled via patch_diag_posix.py,
 *  SIL probe instrumentation added via patch_diag_probe.py) */

/* ================================================================
 * GA-07: FAS_ASSERT crash handler
 *
 * Override FAS_StoreAssertLocation to log file/line and exit(1).
 * With FAS_ASSERT_LEVEL=2 (NO_OP), FAS_InfiniteLoop() returns
 * immediately after this function, so we must exit() here.
 *
 * Note: The original macro only passes __LINE__ (not __FILE__),
 * but the line number + pc value still helps locate the assertion.
 * Exclude fassert.c from Makefile to avoid duplicate symbol.
 * ================================================================ */
void FAS_StoreAssertLocation(uint32_t *pc, uint32_t line) {
    fprintf(stderr, "\n[FAS_ASSERT] ASSERTION FAILED at pc=%p line=%u\n", (void *)pc, line);
    fprintf(stderr, "[FAS_ASSERT] This would be a crash in production. Exiting.\n");
    fflush(stderr);
    exit(1);
}

/* I2C blocking stubs */
uint32_t I2C_Write(void *i2c, uint32_t addr, uint32_t len, uint8_t *data) {
    (void)i2c; (void)addr; (void)len; (void)data; return 0u;
}
uint32_t I2C_Read(void *i2c, uint32_t addr, uint32_t len, uint8_t *data) {
    (void)i2c; (void)addr; (void)len; (void)data; return 0u;
}

/* NXP FS85xx SBC stubs */
void *spi_sbcMcuInterface = NULL;

/* Dummy hardware register RAM — ALL TMS570 register bases redirected to RAM */
#define REG_BUF(name) char name[4096] __attribute__((aligned(4))) = {0}
REG_BUF(posix_adcreg1); REG_BUF(posix_adcreg2);
REG_BUF(posix_canreg1); REG_BUF(posix_canreg2); REG_BUF(posix_canreg3); REG_BUF(posix_canreg4);
REG_BUF(posix_ccmr5reg);
REG_BUF(posix_crcreg1); REG_BUF(posix_crcreg2);
REG_BUF(posix_dccreg1); REG_BUF(posix_dccreg2);
REG_BUF(posix_dmaramreg); REG_BUF(posix_dmareg); REG_BUF(posix_dmmreg);
REG_BUF(posix_efcreg); REG_BUF(posix_emifreg); REG_BUF(posix_epcreg1);
REG_BUF(posix_eqepreg1); REG_BUF(posix_eqepreg2);
REG_BUF(posix_esmreg);
REG_BUF(posix_etpwmreg1); REG_BUF(posix_etpwmreg2); REG_BUF(posix_etpwmreg3);
REG_BUF(posix_etpwmreg4); REG_BUF(posix_etpwmreg5); REG_BUF(posix_etpwmreg6); REG_BUF(posix_etpwmreg7);
REG_BUF(posix_htureg1); REG_BUF(posix_htureg2);
REG_BUF(posix_i2creg1); REG_BUF(posix_i2creg2);
REG_BUF(posix_nmpu_dmareg); REG_BUF(posix_nmpu_emacreg); REG_BUF(posix_nmpu_ps_scr_sreg);
REG_BUF(posix_pcrreg1); REG_BUF(posix_pcrreg2); REG_BUF(posix_pcrreg3);
REG_BUF(posix_pmmreg); REG_BUF(posix_pomreg);
REG_BUF(posix_scmreg1);
REG_BUF(posix_spireg1); REG_BUF(posix_spireg2); REG_BUF(posix_spireg3); REG_BUF(posix_spireg4); REG_BUF(posix_spireg5);
REG_BUF(posix_stcreg1); REG_BUF(posix_stcreg2);
/* Additional registers not in HL_reg_*.h but accessed by foxBMS */
REG_BUF(posix_systemreg1); REG_BUF(posix_systemreg2);
REG_BUF(posix_flashwreg);
REG_BUF(posix_gioporta); REG_BUF(posix_gioportb);
REG_BUF(posix_hetreg1); REG_BUF(posix_hetreg2);
REG_BUF(posix_linreg1); REG_BUF(posix_linreg2);
REG_BUF(posix_scireg1); REG_BUF(posix_scireg3); REG_BUF(posix_scireg4);
REG_BUF(posix_vimreg);
REG_BUF(posix_ecapreg1);
#undef REG_BUF

/* SBC stubs (sbc.c + nxpfs85xx.c excluded) */
typedef enum { SBC_OK = 0 } SBC_RETURN_TYPE_e;
typedef enum { SBC_STATEMACHINE_RUNNING = 2 } SBC_STATEMACHINE_e;
typedef struct { uint8_t dummy; } SBC_STATE_s;
SBC_STATE_s sbc_stateMcuSupervisor = {0};
SBC_RETURN_TYPE_e SBC_SetStateRequest(SBC_STATE_s *p, uint8_t req) { (void)p; (void)req; return SBC_OK; }
SBC_STATEMACHINE_e SBC_GetState(SBC_STATE_s *p) { (void)p; return SBC_STATEMACHINE_RUNNING; }
void SBC_Trigger(SBC_STATE_s *p) { (void)p; }

/* ================================================================
 * PHY
 * ================================================================ */

/* PHY_Initialize defined in real dp83869.c */

/* ================================================================
 * CRC (software implementation replacing hardware CRC peripheral)
 * ================================================================ */

uint64_t CRC_CalculateCrc(uint64_t *pCrc, const uint8_t *pData, uint32_t lengthInBytes)
{
    /* Simple software CRC-64 stub — returns a dummy CRC */
    uint64_t crc = 0xFFFFFFFFFFFFFFFFULL;
    for (uint32_t i = 0u; i < lengthInBytes; i++) {
        crc ^= (uint64_t)pData[i];
        for (int j = 0; j < 8; j++) {
            if (crc & 1ULL) {
                crc = (crc >> 1) ^ 0xC96C5795D7870F42ULL;
            } else {
                crc >>= 1;
            }
        }
    }
    if (pCrc != NULL) { *pCrc = crc; }
    return crc;
}

/* ================================================================
 * IO Pin Access (stubs for register dereferences)
 * ================================================================ */

void IO_PinSet(volatile uint32_t *pRegAddr, uint32_t pin) { (void)pRegAddr; (void)pin; }
void IO_PinReset(volatile uint32_t *pRegAddr, uint32_t pin) { (void)pRegAddr; (void)pin; }
uint32_t IO_PinGet(volatile uint32_t *pRegAddr, uint32_t pin) { (void)pRegAddr; (void)pin; return 0u; }
void IO_SetPinDirectionToInput(volatile uint32_t *pRegAddr, uint32_t pin) { (void)pRegAddr; (void)pin; }
void IO_SetPinDirectionToOutput(volatile uint32_t *pRegAddr, uint32_t pin) { (void)pRegAddr; (void)pin; }

/* ================================================================
 * Additional HAL stubs (from linker error list)
 * ================================================================ */

uint32_t canGetID(void *node, uint32_t mb) {
    (void)node;
    if (mb > 0u && mb <= CAN_MAX_MAILBOXES) return can_mailbox_id[mb - 1u];
    return 0u;
}
void canUpdateID(void *node, uint32_t mb, uint32_t arb) {
    (void)node;
    /* Extract standard 11-bit ID from ARB register format: bits [28:18] */
    uint32_t id = (arb >> 18u) & 0x7FFu;
    if (mb > 0u && mb <= CAN_MAX_MAILBOXES) can_mailbox_id[mb - 1u] = id;
}

void _coreEnableEventBusExport_(void) {}
void _coreEnableIrqVicOffset_(void) {}
void _coreInitRegisters_(void) {}
void _coreInitStackPointer_(void) {}
void _memInit_(void) {}
void _mpuInit_(void) {}

void dmaEnable(void) {}
void dmaEnableInterrupt(uint32_t ch, uint32_t type) { (void)ch; (void)type; }
void dmaReqAssign(uint32_t ch, uint32_t req) { (void)ch; (void)req; }
void dmaSetChEnable(uint32_t ch, uint32_t type) { (void)ch; (void)type; }
void dmaSetCtrlPacket(uint32_t ch, void *ctrl) { (void)ch; (void)ctrl; }

uint32_t ecapGetCAP1(void *ecap) { (void)ecap; return 0u; }
uint32_t ecapGetCAP2(void *ecap) { (void)ecap; return 0u; }
uint32_t ecapGetCAP3(void *ecap) { (void)ecap; return 0u; }
void ecapInit(void) {}
void esmInit(void) {}
void vimInit(void) {}

uint32_t etpwm1GetConfigValue(void *a, uint32_t b) { (void)a; (void)b; return 0u; }
void etpwmSetCmpA(void *a, uint16_t b) { (void)a; (void)b; }
void etpwmStartTBCLK(void) {}
void etpwmStopTBCLK(void) {}

void FAS_DisableInterrupts(void) {}
void FSYS_RaisePrivilege(void) { /* no-op on POSIX */ }

uint32_t MDIOPhyAliveStatusGet(uint32_t base) { (void)base; return 0u; }
uint32_t MDIOPhyRegRead(uint32_t base, uint32_t phy, uint32_t reg, uint16_t *data) {
    (void)base; (void)phy; (void)reg; (void)data; return 0u;
}
void MDIOPhyRegWrite(uint32_t base, uint32_t phy, uint32_t reg, uint16_t data) {
    (void)base; (void)phy; (void)reg; (void)data;
}

void spi1GetConfigValue(void *a, uint32_t b) { (void)a; (void)b; }
void spi2GetConfigValue(void *a, uint32_t b) { (void)a; (void)b; }
void spi3GetConfigValue(void *a, uint32_t b) { (void)a; (void)b; }
void spi4GetConfigValue(void *a, uint32_t b) { (void)a; (void)b; }
void spi5GetConfigValue(void *a, uint32_t b) { (void)a; (void)b; }
void SPI_InitializeChipSelectsAfe(void) {}
void spiSetFunctional(void *node, uint32_t val) { (void)node; (void)val; }
uint32_t spiTransmitAndReceiveData(void *node, void *cfg, uint32_t len, uint16_t *tx, uint16_t *rx) {
    (void)node; (void)cfg; (void)len; (void)tx; (void)rx; return 0u;
}
uint32_t SpiTxStatus(void *node) { (void)node; return 1u; /* complete */ }

void __TI_auto_init(void) { fprintf(stderr, "[POSIX] __TI_auto_init()\n"); fflush(stderr); }
void vPortTaskUsesFPU(void) {}

/* posix_inject_cell_data() was removed — dead code.
 * Cell data reaches foxBMS via CAN path: plant_model.py → 0x270/0x280 → ring buffer → AFE.
 * If direct DB injection is needed later, implement via DATA_WRITE_DATA() with correct struct layout. */

/* portGET_HIGHEST_PRIORITY, portRECORD_READY_PRIORITY, portRESET_READY_PRIORITY
 * now defined as macros in posix_overrides.h using __builtin_clz */

/* ================================================================
 * GA-05: SPS (Smart Power Switch) — realistic contactor simulation
 *
 * Real contactors have 5-20ms mechanical delay. This simulation adds a
 * configurable per-channel delay counter. When requested state changes,
 * a counter starts. After SPS_CONTACTOR_DELAY_CYCLES cycles (default 10,
 * ~10ms at 1ms loop rate), actual state is updated to match requested.
 * ================================================================ */
#define SPS_MAX_CHANNELS 16u

/* Configurable delay: number of SPS_Ctrl() calls before actual follows requested.
 * Default 10 = ~10ms at 1ms task rate. Override via compile flag if needed. */
#ifndef SPS_CONTACTOR_DELAY_CYCLES
#define SPS_CONTACTOR_DELAY_CYCLES 10u
#endif

static uint8_t  sps_channel_requested_state[SPS_MAX_CHANNELS] = {0};
static uint8_t  sps_channel_actual_state[SPS_MAX_CHANNELS]    = {0}; /* 0=OPEN, 1=CLOSED */
static uint8_t  sps_channel_pending[SPS_MAX_CHANNELS]         = {0}; /* 1 = transition in progress */
static uint32_t sps_channel_delay_ctr[SPS_MAX_CHANNELS]       = {0}; /* counts up to SPS_CONTACTOR_DELAY_CYCLES */

void SPS_Initialize(void) {
    fprintf(stderr, "[POSIX] SPS_Initialize() — contactor sim (delay=%u cycles)\n",
            (unsigned)SPS_CONTACTOR_DELAY_CYCLES);
    fflush(stderr);
    memset(sps_channel_requested_state, 0, sizeof(sps_channel_requested_state));
    memset(sps_channel_actual_state,    0, sizeof(sps_channel_actual_state));
    memset(sps_channel_pending,         0, sizeof(sps_channel_pending));
    memset(sps_channel_delay_ctr,       0, sizeof(sps_channel_delay_ctr));
}

void SPS_Ctrl(void) {
    /* Per-channel: if a transition is pending, count down.
     * When counter expires, apply requested→actual and log. */
    for (uint8_t i = 0u; i < SPS_MAX_CHANNELS; i++) {
        /* SIL override: force contactor state */
        if (sil_override_active(SIL_SPS_FORCE, i)) {
            sps_channel_actual_state[i] = (uint8_t)sil_override_get_i32(SIL_SPS_FORCE, i);
            sps_channel_pending[i] = 0u;
            continue;
        }
        if (sps_channel_pending[i] != 0u) {
            sps_channel_delay_ctr[i]++;
            if (sps_channel_delay_ctr[i] >= SPS_CONTACTOR_DELAY_CYCLES) {
                uint8_t old_state = sps_channel_actual_state[i];
                sps_channel_actual_state[i] = sps_channel_requested_state[i];
                sps_channel_pending[i]      = 0u;
                sps_channel_delay_ctr[i]    = 0u;
                fprintf(stderr, "[SPS] Contactor ch=%u %s→%s (after %u-cycle delay)\n",
                        i,
                        old_state ? "CLOSED" : "OPEN",
                        sps_channel_actual_state[i] ? "CLOSED" : "OPEN",
                        (unsigned)SPS_CONTACTOR_DELAY_CYCLES);
                fflush(stderr);
            }
        }
    }

    /* SIL probes: publish SPS state */
    {
        uint16_t actual = 0u, requested = 0u, pending = 0u;
        for (uint8_t i = 0u; i < SPS_MAX_CHANNELS; i++) {
            if (sps_channel_actual_state[i]) actual |= (1u << i);
            if (sps_channel_requested_state[i]) requested |= (1u << i);
            if (sps_channel_pending[i]) pending |= (1u << i);
        }
        sil_probe_4u16(SIL_PROBE_SPS_STATE, actual, requested, 0u, 0u);
        sil_probe_4u16(SIL_PROBE_SPS_PENDING, pending, 0u, 0u, 0u);
    }
}

void SPS_RequestContactorState(uint8_t ch, uint8_t state) {
    if (ch < SPS_MAX_CHANNELS) {
        if (state != sps_channel_requested_state[ch]) {
            sps_channel_requested_state[ch] = state;
            sps_channel_pending[ch]         = 1u;
            sps_channel_delay_ctr[ch]       = 0u;
            fprintf(stderr, "[SPS] RequestContactor ch=%u → %s (pending %u-cycle delay)\n",
                    ch, state ? "CLOSE" : "OPEN",
                    (unsigned)SPS_CONTACTOR_DELAY_CYCLES);
            fflush(stderr);
        }
    }
}
uint8_t SPS_GetChannelFeedback(uint8_t ch) {
    if (ch < SPS_MAX_CHANNELS) return sps_channel_actual_state[ch];
    return 0u;
}
uint8_t SPS_GetChannelAffiliation(uint8_t ch) { (void)ch; return 0u; }
uint8_t SPS_GetChannelCurrentValue(uint8_t ch) { (void)ch; return 0u; }
void SPS_RequestGioState(uint8_t ch, uint8_t state) { (void)ch; (void)state; }
uint8_t SPS_GetGioState(uint8_t ch) { (void)ch; return 0u; }
uint8_t SPS_GetChannelPexFeedback(uint8_t ch) {
    /* Contactor feedback via PEX — return actual state from simulation */
    if (ch < SPS_MAX_CHANNELS) return sps_channel_actual_state[ch];
    return 0u;
}
uint8_t SPS_GetChannelCurrentFeedback(uint8_t ch) {
    if (ch < SPS_MAX_CHANNELS) return sps_channel_actual_state[ch];
    return 0u;
}
void SPS_SwitchOffAllGeneralIoChannels(void) {
    memset(sps_channel_requested_state, 0, sizeof(sps_channel_requested_state));
    memset(sps_channel_actual_state,    0, sizeof(sps_channel_actual_state));
    memset(sps_channel_pending,         0, sizeof(sps_channel_pending));
    memset(sps_channel_delay_ctr,       0, sizeof(sps_channel_delay_ctr));
}

/* Version info */
const char ver_foxbmsBuildConfiguration[] = "posix-debug";
const char ver_versionInformation[] = "foxBMS-POSIX v1.10.0";

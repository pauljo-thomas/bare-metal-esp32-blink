/*
 * Complete ROM-loaded ESP32 blink firmware.  No C runtime and no linker are
 * used: every address is a fixed hardware address and every branch is local.
 */
    .section .text, "ax", @progbits
    .global _start
    .type _start, @function

    .literal .stack_top,       0x3ffb1000
    .literal .wdt_key,         0x50d83aa1
    .literal .bit31,           0x80000000
    .literal .rtc_wprotect,    0x3ff480a4
    .literal .rtc_feed,        0x3ff480a0
    .literal .rtc_config0,     0x3ff4808c
    .literal .tg0_wprotect,    0x3ff5f064
    .literal .tg0_config0,     0x3ff5f048
    .literal .tg1_wprotect,    0x3ff60064
    .literal .tg1_config0,     0x3ff60048
    .literal .t0_config,       0x3ff5f000
    .literal .t0_lo,           0x3ff5f004
    .literal .t0_hi,           0x3ff5f008
    .literal .t0_update,       0x3ff5f00c
    .literal .t0_config_value, 0x400a0000 /* up-counter, peripheral clock / 80 */
    /* This board's ROM boot clock leaves Timer Group 0 at 500 kHz. */
    .literal .one_second_less1, 499999
    .literal .gpio2_mux,       0x3ff49040
    .literal .gpio2_matrix,    0x3ff44538
    .literal .gpio_out_set,    0x3ff44008
    .literal .gpio_out_clear,  0x3ff4400c
    .literal .gpio_enable_set, 0x3ff44024
    .literal .mux_function_mask, 0xffff8fff

_start:
    l32r    a1, .stack_top

    /* Disable the RTC watchdog inherited from the ROM boot flow. */
    l32r    a2, .rtc_wprotect
    l32r    a3, .wdt_key
    s32i    a3, a2, 0
    l32r    a2, .rtc_feed
    l32r    a3, .bit31
    s32i    a3, a2, 0
    l32r    a2, .rtc_config0
    movi    a3, 0
    s32i    a3, a2, 0
    l32r    a2, .rtc_wprotect
    s32i    a3, a2, 0

    /* Disable watchdogs in Timer Groups 0 and 1. */
    l32r    a2, .tg0_wprotect
    l32r    a3, .wdt_key
    s32i    a3, a2, 0
    l32r    a2, .tg0_config0
    movi    a3, 0
    s32i    a3, a2, 0
    l32r    a2, .tg0_wprotect
    s32i    a3, a2, 0
    l32r    a2, .tg1_wprotect
    l32r    a3, .wdt_key
    s32i    a3, a2, 0
    l32r    a2, .tg1_config0
    movi    a3, 0
    s32i    a3, a2, 0
    l32r    a2, .tg1_wprotect
    s32i    a3, a2, 0

    /* Timer Group 0, timer 0: start a one-microsecond counter. */
    l32r    a2, .t0_config
    l32r    a3, .t0_config_value
    s32i    a3, a2, 0
    l32r    a2, .t0_lo
    movi    a3, 0
    s32i    a3, a2, 0
    l32r    a2, .t0_hi
    s32i    a3, a2, 0
    l32r    a2, .t0_config
    l32i    a3, a2, 0
    l32r    a4, .bit31
    or      a3, a3, a4
    s32i    a3, a2, 0

    /* Configure GPIO2 as a direct GPIO output. */
    l32r    a2, .gpio2_mux
    l32i    a3, a2, 0
    l32r    a4, .mux_function_mask
    and     a3, a3, a4
    movi    a4, 1
    slli    a4, a4, 13
    or      a3, a3, a4
    s32i    a3, a2, 0
    l32r    a2, .gpio2_matrix
    movi    a3, 256
    s32i    a3, a2, 0
    movi    a3, 4
    l32r    a2, .gpio_out_clear
    s32i    a3, a2, 0
    l32r    a2, .gpio_enable_set
    s32i    a3, a2, 0

.blink:
    l32r    a2, .gpio_out_set
    s32i    a3, a2, 0
    l32r    a4, .t0_update
    l32r    a5, .t0_lo
    movi    a6, 1
    s32i    a6, a4, 0
    l32i    a7, a5, 0
    l32r    a8, .one_second_less1
.wait_high:
    s32i    a6, a4, 0
    l32i    a9, a5, 0
    sub     a9, a9, a7
    bgeu    a8, a9, .wait_high
    l32r    a2, .gpio_out_clear
    s32i    a3, a2, 0
    l32r    a4, .t0_update
    l32r    a5, .t0_lo
    movi    a6, 1
    s32i    a6, a4, 0
    l32i    a7, a5, 0
    l32r    a8, .one_second_less1
.wait_low:
    s32i    a6, a4, 0
    l32i    a9, a5, 0
    sub     a9, a9, a7
    bgeu    a8, a9, .wait_low
    j       .blink

    .size _start, . - _start

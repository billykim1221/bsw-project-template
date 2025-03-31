/**
 * BSW Project Template — LED Blink (Hello World)
 * Target: LP-MSPM0G3507 (MSPM0G series, Cortex-M0+)
 *
 * Blinks LED_GREEN (PA0) at 1 Hz via BSW tick timer.
 */

#include "Dio.h"
#include "Mcu.h"
#include "Os.h"

#define LED_GREEN_CHANNEL   DioConf_DioChannel_LED_GREEN
#define BLINK_PERIOD_MS     500u

int main(void)
{
    Mcu_Init(NULL_PTR);
    Dio_Init(NULL_PTR);
    Os_Init();

    for (;;)
    {
        Dio_WriteChannel(LED_GREEN_CHANNEL, STD_HIGH);
        Os_DelayMs(BLINK_PERIOD_MS);
        Dio_WriteChannel(LED_GREEN_CHANNEL, STD_LOW);
        Os_DelayMs(BLINK_PERIOD_MS);
    }

    return 0;
}

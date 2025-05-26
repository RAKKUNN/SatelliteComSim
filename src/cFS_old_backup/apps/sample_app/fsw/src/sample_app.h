#ifndef SAMPLE_APP_H
#define SAMPLE_APP_H

/*
** Required header files.
*/
#include "cfe.h"
#include "cfe_config.h"

#include "sample_app_mission_cfg.h"
#include "sample_app_platform_cfg.h"

#include "sample_app_perfids.h"
#include "sample_app_msgids.h"
#include "sample_app_msg.h"

/************************************************************************
** Type Definitions
*************************************************************************/

typedef struct
{
    /*
    ** Command interface counters...
    */
    uint8 CmdCounter;
    uint8 ErrCounter;

    /*
    ** Housekeeping telemetry packet...
    */
    SAMPLE_APP_HkTlm_t HkTlm;

    /*
    ** Plaintext telemetry packet (추가된 항목)
    */
    SAMPLE_PlainTextTlm_t TextTlm;

    /*
    ** Run Status variable used in the main processing loop
    */
    uint32 RunStatus;

    /*
    ** Operational data (not reported in housekeeping)...
    */
    CFE_SB_PipeId_t CommandPipe;

    /*
    ** Initialization data (not reported in housekeeping)...
    */
    char   PipeName[CFE_MISSION_MAX_API_LEN];
    uint16 PipeDepth;

    CFE_TBL_Handle_t TblHandles[SAMPLE_APP_NUMBER_OF_TABLES];
} SAMPLE_APP_Data_t;

extern SAMPLE_APP_Data_t SAMPLE_APP_Data;

void SAMPLE_APP_Main(void);
CFE_Status_t SAMPLE_APP_Init(void);

#endif /* SAMPLE_APP_H */


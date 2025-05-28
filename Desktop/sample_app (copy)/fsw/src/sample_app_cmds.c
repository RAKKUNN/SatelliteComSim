/************************************************************************
 * NASA Docket No. GSC-18,719-1, and identified as “core Flight System: Bootes”
 *
 * Copyright (c) 2020 United States Government as represented by the
 * Administrator of the National Aeronautics and Space Administration.
 * All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ************************************************************************/

/**
 * \file
 *   This file contains the source code for the Sample App Ground Command-handling functions
 */

/*
** Include Files:
*/
#include "sample_app.h"
#include "sample_app_cmds.h"
#include "sample_app_msgids.h"
#include "sample_app_eventids.h"
#include "sample_app_version.h"
#include "sample_app_tbl.h"
#include "sample_app_utils.h"
#include "sample_app_msg.h"

#include "sample_lib.h"

CFE_Status_t SAMPLE_APP_SendHkCmd(const SAMPLE_APP_SendHkCmd_t *Msg)
{
    int i;

    SAMPLE_APP_Data.HkTlm.Payload.CommandErrorCounter = SAMPLE_APP_Data.ErrCounter;
    SAMPLE_APP_Data.HkTlm.Payload.CommandCounter      = SAMPLE_APP_Data.CmdCounter;

    CFE_SB_TimeStampMsg(CFE_MSG_PTR(SAMPLE_APP_Data.HkTlm.TelemetryHeader));
    CFE_SB_TransmitMsg(CFE_MSG_PTR(SAMPLE_APP_Data.HkTlm.TelemetryHeader), true);

    for (i = 0; i < SAMPLE_APP_NUMBER_OF_TABLES; i++)
    {
        CFE_TBL_Manage(SAMPLE_APP_Data.TblHandles[i]);
    }

    return CFE_SUCCESS;
}

CFE_Status_t SAMPLE_APP_NoopCmd(const SAMPLE_APP_NoopCmd_t *Msg)
{
    SAMPLE_APP_Data.CmdCounter++;

    CFE_EVS_SendEvent(SAMPLE_APP_NOOP_INF_EID, CFE_EVS_EventType_INFORMATION, "SAMPLE: NOOP command %s",
                      SAMPLE_APP_VERSION);

    return CFE_SUCCESS;
}

CFE_Status_t SAMPLE_APP_ResetCountersCmd(const SAMPLE_APP_ResetCountersCmd_t *Msg)
{
    SAMPLE_APP_Data.CmdCounter = 0;
    SAMPLE_APP_Data.ErrCounter = 0;

    CFE_EVS_SendEvent(SAMPLE_APP_RESET_INF_EID, CFE_EVS_EventType_INFORMATION, "SAMPLE: RESET command");

    return CFE_SUCCESS;
}

CFE_Status_t SAMPLE_APP_ProcessCmd(const SAMPLE_APP_ProcessCmd_t *Msg)
{
    CFE_Status_t               status;
    void *                     TblAddr;
    SAMPLE_APP_ExampleTable_t *TblPtr;
    const char *               TableName = "SAMPLE_APP.ExampleTable";

    status = CFE_TBL_GetAddress(&TblAddr, SAMPLE_APP_Data.TblHandles[0]);

    if (status < CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Fail to get table address: 0x%08lx", (unsigned long)status);
        return status;
    }

    TblPtr = TblAddr;
    CFE_ES_WriteToSysLog("Sample App: Example Table Value 1: %d  Value 2: %d", TblPtr->Int1, TblPtr->Int2);

    SAMPLE_APP_GetCrc(TableName);

    status = CFE_TBL_ReleaseAddress(SAMPLE_APP_Data.TblHandles[0]);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Fail to release table address: 0x%08lx", (unsigned long)status);
        return status;
    }

    SAMPLE_LIB_Function();

    return CFE_SUCCESS;
}

CFE_Status_t SAMPLE_APP_DisplayParamCmd(const SAMPLE_APP_DisplayParamCmd_t *Msg)
{
    CFE_EVS_SendEvent(SAMPLE_APP_VALUE_INF_EID, CFE_EVS_EventType_INFORMATION,
                      "SAMPLE_APP: ValU32=%lu, ValI16=%d, ValStr=%s", (unsigned long)Msg->Payload.ValU32,
                      (int)Msg->Payload.ValI16, Msg->Payload.ValStr);

    return CFE_SUCCESS;
}

// ✅ 새로 추가된 평문 수신 및 응답 함수
CFE_Status_t SAMPLE_SendText(const SAMPLE_SendTextCmd_t *Msg)
{
    CFE_EVS_SendEvent(100, CFE_EVS_EventType_INFORMATION,
                      "Received plain text: %s", Msg->PlainText);

    strncpy(SAMPLE_APP_Data.TextTlm.PlainText, Msg->PlainText, sizeof(SAMPLE_APP_Data.TextTlm.PlainText));

    CFE_SB_TimeStampMsg(CFE_MSG_PTR(SAMPLE_APP_Data.TextTlm.TlmHeader));
    CFE_SB_TransmitMsg(CFE_MSG_PTR(SAMPLE_APP_Data.TextTlm.TlmHeader), true);

    return CFE_SUCCESS;
}


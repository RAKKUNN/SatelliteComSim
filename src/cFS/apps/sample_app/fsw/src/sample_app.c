/*******************************************************************************
**
**      GSC-18128-1, "Core Flight Executive Version 6.7"
**
**      Copyright (c) 2006-2019 United States Government as represented by
**      the Administrator of the National Aeronautics and Space Administration.
**      All Rights Reserved.
**
**      Licensed under the Apache License, Version 2.0 (the "License");
**      you may not use this file except in compliance with the License.
**      You may obtain a copy of the License at
**
**        http://www.apache.org/licenses/LICENSE-2.0
**
**      Unless required by applicable law or agreed to in writing, software
**      distributed under the License is distributed on an "AS IS" BASIS,
**      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
**      See the License for the specific language governing permissions and
**      limitations under the License.
**
** File: sample_app.c
**
** Purpose:
**   This file contains the source code for the Sample App.
**
*******************************************************************************/

/*
** Include Files:
*/
#include "sample_app_events.h"
#include "sample_app_version.h"
#include "sample_app.h"
#include "sample_app_table.h"

#include <string.h>
#include <stddef.h>

#include "sample_lib.h"
#include "sample_app_msg.h"

/*
** local helpers
*/
static size_t SAMPLE_Strnlen(const char *s, size_t maxn)
{
    size_t n = 0;
    while (n < maxn && s[n] != '\0')
    {
        ++n;
    }
    return n;
}

/*
** global data
*/
SAMPLE_AppData_t SAMPLE_AppData;

/* Text telemetry buffer (MsgHdr는 바이트 배열 헤더) */
static SAMPLE_TextTlm_t SAMPLE_TextTlmBuf;

/* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *  * *  * * * * **/
/* SAMPLE_AppMain() -- Application entry point and main process loop          */
/*                                                                            */
/* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *  * *  * * * * **/
void SAMPLE_AppMain(void)
{
    int32 status;

    /*
    ** Register the app with Executive services
    */
    CFE_ES_RegisterApp();

    /*
    ** Create the first Performance Log entry
    */
    CFE_ES_PerfLogEntry(SAMPLE_APP_PERF_ID);

    /*
    ** Perform application specific initialization
    ** If the Initialization fails, set the RunStatus to
    ** CFE_ES_RunStatus_APP_ERROR and the App will not enter the RunLoop
    */
    status = SAMPLE_AppInit();
    if (status != CFE_SUCCESS)
    {
        SAMPLE_AppData.RunStatus = CFE_ES_RunStatus_APP_ERROR;
    }

    /*
    ** SAMPLE Runloop
    */
    while (CFE_ES_RunLoop(&SAMPLE_AppData.RunStatus) == true)
    {
        /*
        ** Performance Log Exit Stamp
        */
        CFE_ES_PerfLogExit(SAMPLE_APP_PERF_ID);

        /* Pend on receipt of command packet */
        status = CFE_SB_RcvMsg(&SAMPLE_AppData.MsgPtr,
                               SAMPLE_AppData.CommandPipe,
                               CFE_SB_PEND_FOREVER);

        /*
        ** Performance Log Entry Stamp
        */
        CFE_ES_PerfLogEntry(SAMPLE_APP_PERF_ID);

        if (status == CFE_SUCCESS)
        {
            SAMPLE_ProcessCommandPacket(SAMPLE_AppData.MsgPtr);
        }
        else
        {
            CFE_EVS_SendEvent(SAMPLE_PIPE_ERR_EID,
                              CFE_EVS_EventType_ERROR,
                              "SAMPLE APP: SB Pipe Read Error, App Will Exit");

            SAMPLE_AppData.RunStatus = CFE_ES_RunStatus_APP_ERROR;
        }
    }

    /*
    ** Performance Log Exit Stamp
    */
    CFE_ES_PerfLogExit(SAMPLE_APP_PERF_ID);

    CFE_ES_ExitApp(SAMPLE_AppData.RunStatus);

} /* End of SAMPLE_AppMain() */

/* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *  */
/*                                                                            */
/* SAMPLE_AppInit() --  initialization                                        */
/*                                                                            */
/* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * **/
int32 SAMPLE_AppInit(void)
{
    int32 status;

    SAMPLE_AppData.RunStatus = CFE_ES_RunStatus_APP_RUN;

    /*
    ** Initialize app command execution counters
    */
    SAMPLE_AppData.CmdCounter = 0;
    SAMPLE_AppData.ErrCounter = 0;

    /*
    ** Initialize app configuration data
    */
    SAMPLE_AppData.PipeDepth = SAMPLE_PIPE_DEPTH;

    strcpy(SAMPLE_AppData.PipeName, "SAMPLE_CMD_PIPE");

    /*
    ** Initialize event filter table...
    */
    SAMPLE_AppData.EventFilters[0].EventID = SAMPLE_STARTUP_INF_EID;
    SAMPLE_AppData.EventFilters[0].Mask    = 0x0000;
    SAMPLE_AppData.EventFilters[1].EventID = SAMPLE_COMMAND_ERR_EID;
    SAMPLE_AppData.EventFilters[1].Mask    = 0x0000;
    SAMPLE_AppData.EventFilters[2].EventID = SAMPLE_COMMANDNOP_INF_EID;
    SAMPLE_AppData.EventFilters[2].Mask    = 0x0000;
    SAMPLE_AppData.EventFilters[3].EventID = SAMPLE_COMMANDRST_INF_EID;
    SAMPLE_AppData.EventFilters[3].Mask    = 0x0000;
    SAMPLE_AppData.EventFilters[4].EventID = SAMPLE_INVALID_MSGID_ERR_EID;
    SAMPLE_AppData.EventFilters[4].Mask    = 0x0000;
    SAMPLE_AppData.EventFilters[5].EventID = SAMPLE_LEN_ERR_EID;
    SAMPLE_AppData.EventFilters[5].Mask    = 0x0000;
    SAMPLE_AppData.EventFilters[6].EventID = SAMPLE_PIPE_ERR_EID;
    SAMPLE_AppData.EventFilters[6].Mask    = 0x0000;

    /*
    ** Register the events
    */
    status = CFE_EVS_Register(SAMPLE_AppData.EventFilters,
                              SAMPLE_EVENT_COUNTS,
                              CFE_EVS_EventFilter_BINARY);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Error Registering Events, RC = 0x%08lX\n",
                             (unsigned long)status);
        return status;
    }

    /*
    ** Initialize housekeeping packet (clear user data area).
    */
    CFE_SB_InitMsg(&SAMPLE_AppData.HkBuf.MsgHdr,
                   SAMPLE_APP_HK_TLM_MID,
                   sizeof(SAMPLE_AppData.HkBuf),
                   true);

    /*
    ** Initialize text telemetry packet
    **  (MsgHdr는 바이트 배열이므로 그 주소를 직접 넘긴다)
    */
    CFE_SB_InitMsg(&SAMPLE_TextTlmBuf.MsgHdr,
                   SAMPLE_APP_TEXT_TLM_MID,
                   sizeof(SAMPLE_TextTlm_t),
                   true);
    SAMPLE_TextTlmBuf.TextLen = 0;
    memset(SAMPLE_TextTlmBuf.Text, 0, SAMPLE_APP_TEXT_MAX_LEN);

    /*
    ** Create Software Bus message pipe.
    */
    status = CFE_SB_CreatePipe(&SAMPLE_AppData.CommandPipe,
                               SAMPLE_AppData.PipeDepth,
                               SAMPLE_AppData.PipeName);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Error creating pipe, RC = 0x%08lX\n",
                             (unsigned long)status);
        return status;
    }

    /*
    ** Subscribe to Housekeeping request commands
    */
    status = CFE_SB_Subscribe(SAMPLE_APP_SEND_HK_MID,
                              SAMPLE_AppData.CommandPipe);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Error Subscribing to HK request, RC = 0x%08lX\n",
                             (unsigned long)status);
        return status;
    }

    /*
    ** Subscribe to ground command packets
    */
    status = CFE_SB_Subscribe(SAMPLE_APP_CMD_MID,
                              SAMPLE_AppData.CommandPipe);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Error Subscribing to Command, RC = 0x%08lX\n",
                             (unsigned long)status);
        return status;
    }

    /*
    ** Register Table(s)
    */
    status = CFE_TBL_Register(&SAMPLE_AppData.TblHandles[0],
                              "SampleAppTable",
                              sizeof(SAMPLE_APP_Table_t),
                              CFE_TBL_OPT_DEFAULT,
                              SAMPLE_TblValidationFunc);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Error Registering Table, RC = 0x%08lX\n", (unsigned long)status);
        return status;
    }
    else
    {
        status = CFE_TBL_Load(SAMPLE_AppData.TblHandles[0],
                              CFE_TBL_SRC_FILE,
                              SAMPLE_APP_TABLE_FILE);
    }

    CFE_EVS_SendEvent(SAMPLE_STARTUP_INF_EID,
                      CFE_EVS_EventType_INFORMATION,
                      "SAMPLE App Initialized.%s",
                      SAMPLE_APP_VERSION_STRING);

    return CFE_SUCCESS;

} /* End of SAMPLE_AppInit() */

/* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * **/
/*  Name:  SAMPLE_ProcessCommandPacket                         */
/* * * * * * * * * * * * * * * * * * * * * * * *  * * * * * * */
void SAMPLE_ProcessCommandPacket(CFE_SB_MsgPtr_t Msg)
{
    CFE_SB_MsgId_t MsgId = CFE_SB_GetMsgId(Msg);

    switch (MsgId)
    {
        case SAMPLE_APP_CMD_MID:
            SAMPLE_ProcessGroundCommand(Msg);
            break;

        case SAMPLE_APP_SEND_HK_MID:
            SAMPLE_ReportHousekeeping((CFE_SB_CmdHdr_t *)Msg);
            break;

        default:
            CFE_EVS_SendEvent(SAMPLE_INVALID_MSGID_ERR_EID,
                              CFE_EVS_EventType_ERROR,
                              "SAMPLE: invalid command packet,MID = 0x%x",
                              (unsigned int)CFE_SB_MsgIdToValue(MsgId));
            break;
    }
} /* End SAMPLE_ProcessCommandPacket */

/* * * * * * * * * * * * * * * * * * * * * * * **/
/*  SAMPLE_ProcessGroundCommand()               */
/* * * * * * * * * * * * * * * * * * * * * * * **/
void SAMPLE_ProcessGroundCommand(CFE_SB_MsgPtr_t Msg)
{
    uint16 CommandCode = CFE_SB_GetCmdCode(Msg);

    switch (CommandCode)
    {
        case SAMPLE_APP_NOOP_CC:
            if (SAMPLE_VerifyCmdLength(Msg, sizeof(SAMPLE_Noop_t)))
            {
                SAMPLE_Noop((SAMPLE_Noop_t *)Msg);
            }
            break;

        case SAMPLE_APP_RESET_COUNTERS_CC:
            if (SAMPLE_VerifyCmdLength(Msg, sizeof(SAMPLE_ResetCounters_t)))
            {
                SAMPLE_ResetCounters((SAMPLE_ResetCounters_t *)Msg);
            }
            break;

        case SAMPLE_APP_PROCESS_CC:
            if (SAMPLE_VerifyCmdLength(Msg, sizeof(SAMPLE_Process_t)))
            {
                SAMPLE_Process((SAMPLE_Process_t *)Msg);
            }
            break;

        case SAMPLE_APP_SEND_TEXT_CC:
            if (SAMPLE_VerifyCmdLength(Msg, sizeof(SAMPLE_SendTextCmd_t)))
            {
                const SAMPLE_SendTextCmd_t *cmd = (const SAMPLE_SendTextCmd_t *)Msg;

                /* 안전한 로컬 버퍼로 복사 + NUL 보장 */
                char local[SAMPLE_APP_TEXT_MAX_LEN];
                memcpy(local, cmd->Text, SAMPLE_APP_TEXT_MAX_LEN);
                local[SAMPLE_APP_TEXT_MAX_LEN - 1] = '\0';

                /* 카운터/로그 */
                SAMPLE_AppData.CmdCounter++;
                CFE_EVS_SendEvent(SAMPLE_COMMANDNOP_INF_EID,
                                  CFE_EVS_EventType_INFORMATION,
                                  "SAMPLE: SEND_TEXT received: '%s'", local);

                /* 텍스트 텔레메트리 채워 송신 */
                SAMPLE_TextTlmBuf.TextLen = (uint16)SAMPLE_Strnlen(local, SAMPLE_APP_TEXT_MAX_LEN);
                memset(SAMPLE_TextTlmBuf.Text, 0, SAMPLE_APP_TEXT_MAX_LEN);
                memcpy(SAMPLE_TextTlmBuf.Text, local, SAMPLE_TextTlmBuf.TextLen);

                CFE_SB_TimeStampMsg((CFE_SB_MsgPtr_t)&SAMPLE_TextTlmBuf.MsgHdr);
                CFE_SB_SendMsg((CFE_SB_Msg_t *)&SAMPLE_TextTlmBuf.MsgHdr);
            }
            break;

        default:
            CFE_EVS_SendEvent(SAMPLE_COMMAND_ERR_EID,
                              CFE_EVS_EventType_ERROR,
                              "Invalid ground command code: CC = %d",
                              CommandCode);
            break;
    }
} /* End of SAMPLE_ProcessGroundCommand() */

/* * * * * * * * * * * * * * * * * * * * * * * **/
/*  Name:  SAMPLE_ReportHousekeeping            */
/* * * * * * * * * * * * * * * * * * * * * * * **/
int32 SAMPLE_ReportHousekeeping(const CFE_SB_CmdHdr_t *Msg)
{
    int i;

    SAMPLE_AppData.HkBuf.HkTlm.Payload.CommandErrorCounter = SAMPLE_AppData.ErrCounter;
    SAMPLE_AppData.HkBuf.HkTlm.Payload.CommandCounter      = SAMPLE_AppData.CmdCounter;

    CFE_SB_TimeStampMsg(&SAMPLE_AppData.HkBuf.MsgHdr);
    CFE_SB_SendMsg(&SAMPLE_AppData.HkBuf.MsgHdr);

    for (i = 0; i < SAMPLE_NUMBER_OF_TABLES; i++)
    {
        CFE_TBL_Manage(SAMPLE_AppData.TblHandles[i]);
    }

    return CFE_SUCCESS;
} /* End of SAMPLE_ReportHousekeeping() */

/* * * * * * * * * * * * * * * * * * * * * * * **/
/*  SAMPLE_Noop                                 */
/* * * * * * * * * * * * * * * * * * * * * * * **/
int32 SAMPLE_Noop(const SAMPLE_Noop_t *Msg)
{
    SAMPLE_AppData.CmdCounter++;

    CFE_EVS_SendEvent(SAMPLE_COMMANDNOP_INF_EID,
                      CFE_EVS_EventType_INFORMATION,
                      "SAMPLE: NOOP command %s", SAMPLE_APP_VERSION);

    return CFE_SUCCESS;
} /* End of SAMPLE_Noop */

/* * * * * * * * * * * * * * * * * * * * * * * **/
/*  SAMPLE_ResetCounters                        */
/* * * * * * * * * * * * * * * * * * * * * * * **/
int32 SAMPLE_ResetCounters(const SAMPLE_ResetCounters_t *Msg)
{
    SAMPLE_AppData.CmdCounter = 0;
    SAMPLE_AppData.ErrCounter = 0;

    CFE_EVS_SendEvent(SAMPLE_COMMANDRST_INF_EID,
                      CFE_EVS_EventType_INFORMATION,
                      "SAMPLE: RESET command");

    return CFE_SUCCESS;
} /* End of SAMPLE_ResetCounters() */

/* * * * * * * * * * * * * * * * * * * * * * * **/
/*  SAMPLE_Process                              */
/* * * * * * * * * * * * * * * * * * * * * * * **/
int32 SAMPLE_Process(const SAMPLE_Process_t *Msg)
{
    int32 status;
    SAMPLE_APP_Table_t *TblPtr;
    const char *TableName = "SAMPLE_APP.SampleAppTable";

    status = CFE_TBL_GetAddress((void *)&TblPtr, SAMPLE_AppData.TblHandles[0]);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Fail to get table address: 0x%08lx",
                             (unsigned long)status);
        return status;
    }

    CFE_ES_WriteToSysLog("Sample App: Table Value 1: %d  Value 2: %d",
                         TblPtr->Int1,
                         TblPtr->Int2);

    SAMPLE_GetCrc(TableName);

    status = CFE_TBL_ReleaseAddress(SAMPLE_AppData.TblHandles[0]);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Fail to release table address: 0x%08lx",
                             (unsigned long)status);
        return status;
    }

    SAMPLE_Function();

    return CFE_SUCCESS;
} /* End of SAMPLE_ProcessCC */

/* * * * * * * * * * * * * * * * * * * * * * * **/
/*  SAMPLE_VerifyCmdLength                      */
/* * * * * * * * * * * * * * * * * * * * * * * **/
bool SAMPLE_VerifyCmdLength(CFE_SB_MsgPtr_t Msg, uint16 ExpectedLength)
{
    bool result = true;
    uint16 ActualLength = CFE_SB_GetTotalMsgLength(Msg);

    if (ExpectedLength != ActualLength)
    {
        CFE_SB_MsgId_t MessageID   = CFE_SB_GetMsgId(Msg);
        uint16         CommandCode = CFE_SB_GetCmdCode(Msg);

        CFE_EVS_SendEvent(SAMPLE_LEN_ERR_EID,
                          CFE_EVS_EventType_ERROR,
                          "Invalid Msg length: ID = 0x%X,  CC = %d, Len = %d, Expected = %d",
                          (unsigned int)CFE_SB_MsgIdToValue(MessageID),
                          CommandCode,
                          ActualLength,
                          ExpectedLength);

        result = false;
        SAMPLE_AppData.ErrCounter++;
    }

    return result;
} /* End of SAMPLE_VerifyCmdLength() */

/* * * * * * * * * * * * * * * * * * * * * * * **/
/*  SAMPLE_TblValidationFunc                    */
/* * * * * * * * * * * * * * * * * * * * * * * **/
int32 SAMPLE_TblValidationFunc(void *TblData)
{
    int32 ReturnCode = CFE_SUCCESS;
    SAMPLE_APP_Table_t *TblDataPtr = (SAMPLE_APP_Table_t *)TblData;

    if (TblDataPtr->Int1 > SAMPLE_APP_TBL_ELEMENT_1_MAX)
    {
        ReturnCode = SAMPLE_APP_TABLE_OUT_OF_RANGE_ERR_CODE;
    }

    return ReturnCode;
} /* End of SAMPLE_TBLValidationFunc() */

/* * * * * * * * * * * * * * * * * * * * * * * **/
/*  SAMPLE_GetCrc                               */
/* * * * * * * * * * * * * * * * * * * * * * * **/
void SAMPLE_GetCrc(const char *TableName)
{
    int32           status;
    uint32          Crc;
    CFE_TBL_Info_t  TblInfoPtr;

    status = CFE_TBL_GetInfo(&TblInfoPtr, TableName);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Error Getting Table Info");
    }
    else
    {
        Crc = TblInfoPtr.Crc;
        CFE_ES_WriteToSysLog("Sample App: CRC: 0x%08lX\n\n", (unsigned long)Crc);
    }
} /* End of SAMPLE_GetCrc */


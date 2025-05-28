#include "sample_app.h"
#include "sample_app_cmds.h"
#include "sample_app_utils.h"
#include "sample_app_eventids.h"
#include "sample_app_dispatch.h"
#include "sample_app_tbl.h"
#include "sample_app_version.h"

SAMPLE_APP_Data_t SAMPLE_APP_Data;

void SAMPLE_APP_Main(void)
{
    CFE_Status_t     status;
    CFE_SB_Buffer_t *SBBufPtr;

    CFE_ES_PerfLogEntry(SAMPLE_APP_PERF_ID);

    status = SAMPLE_APP_Init();
    if (status != CFE_SUCCESS)
    {
        SAMPLE_APP_Data.RunStatus = CFE_ES_RunStatus_APP_ERROR;
    }

    while (CFE_ES_RunLoop(&SAMPLE_APP_Data.RunStatus) == true)
    {
        CFE_ES_PerfLogExit(SAMPLE_APP_PERF_ID);
        status = CFE_SB_ReceiveBuffer(&SBBufPtr, SAMPLE_APP_Data.CommandPipe, CFE_SB_PEND_FOREVER);
        CFE_ES_PerfLogEntry(SAMPLE_APP_PERF_ID);

        if (status == CFE_SUCCESS)
        {
            SAMPLE_APP_TaskPipe(SBBufPtr);
        }
        else
        {
            CFE_EVS_SendEvent(SAMPLE_APP_PIPE_ERR_EID, CFE_EVS_EventType_ERROR,
                              "SAMPLE APP: SB Pipe Read Error, App Will Exit");
            SAMPLE_APP_Data.RunStatus = CFE_ES_RunStatus_APP_ERROR;
        }
    }

    CFE_ES_PerfLogExit(SAMPLE_APP_PERF_ID);
    CFE_ES_ExitApp(SAMPLE_APP_Data.RunStatus);
}

CFE_Status_t SAMPLE_APP_Init(void)
{
    CFE_Status_t status;
    char         VersionString[SAMPLE_APP_CFG_MAX_VERSION_STR_LEN];

    memset(&SAMPLE_APP_Data, 0, sizeof(SAMPLE_APP_Data));
    SAMPLE_APP_Data.RunStatus = CFE_ES_RunStatus_APP_RUN;
    SAMPLE_APP_Data.PipeDepth = SAMPLE_APP_PIPE_DEPTH;

    strncpy(SAMPLE_APP_Data.PipeName, "SAMPLE_APP_CMD_PIPE", sizeof(SAMPLE_APP_Data.PipeName));
    SAMPLE_APP_Data.PipeName[sizeof(SAMPLE_APP_Data.PipeName) - 1] = 0;

    status = CFE_EVS_Register(NULL, 0, CFE_EVS_EventFilter_BINARY);
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("Sample App: Error Registering Events, RC = 0x%08lX\n", (unsigned long)status);
    }
    else
    {
        // ✅ 기존 Housekeeping 텔레메트리 초기화
        CFE_MSG_Init(CFE_MSG_PTR(SAMPLE_APP_Data.HkTlm.TelemetryHeader),
                     CFE_SB_ValueToMsgId(SAMPLE_APP_HK_TLM_MID),
                     sizeof(SAMPLE_APP_Data.HkTlm));

        // ✅ 추가된 평문 텔레메트리 구조체 초기화
        CFE_MSG_Init(CFE_MSG_PTR(SAMPLE_APP_Data.TextTlm.TlmHeader),
                     CFE_SB_ValueToMsgId(SAMPLE_APP_TEXT_TLM_MID),  // msgids.h에 정의 필요
                     sizeof(SAMPLE_APP_Data.TextTlm));

        // 커맨드 수신 파이프 생성
        status = CFE_SB_CreatePipe(&SAMPLE_APP_Data.CommandPipe, SAMPLE_APP_Data.PipeDepth,
                                   SAMPLE_APP_Data.PipeName);
        if (status != CFE_SUCCESS)
        {
            CFE_EVS_SendEvent(SAMPLE_APP_CR_PIPE_ERR_EID, CFE_EVS_EventType_ERROR,
                              "Sample App: Error creating SB Command Pipe, RC = 0x%08lX", (unsigned long)status);
        }
    }

    if (status == CFE_SUCCESS)
    {
        // 하우스키핑 명령 구독
        status = CFE_SB_Subscribe(CFE_SB_ValueToMsgId(SAMPLE_APP_SEND_HK_MID), SAMPLE_APP_Data.CommandPipe);
        if (status != CFE_SUCCESS)
        {
            CFE_EVS_SendEvent(SAMPLE_APP_SUB_HK_ERR_EID, CFE_EVS_EventType_ERROR,
                              "Sample App: Error Subscribing to HK request, RC = 0x%08lX", (unsigned long)status);
        }
    }

    if (status == CFE_SUCCESS)
    {
        // 명령 메시지 구독
        status = CFE_SB_Subscribe(CFE_SB_ValueToMsgId(SAMPLE_APP_CMD_MID), SAMPLE_APP_Data.CommandPipe);
        if (status != CFE_SUCCESS)
        {
            CFE_EVS_SendEvent(SAMPLE_APP_SUB_CMD_ERR_EID, CFE_EVS_EventType_ERROR,
                              "Sample App: Error Subscribing to Commands, RC = 0x%08lX", (unsigned long)status);
        }
    }

    if (status == CFE_SUCCESS)
    {
        // 예제 테이블 등록
        status = CFE_TBL_Register(&SAMPLE_APP_Data.TblHandles[0], "ExampleTable", sizeof(SAMPLE_APP_ExampleTable_t),
                                  CFE_TBL_OPT_DEFAULT, SAMPLE_APP_TblValidationFunc);
        if (status != CFE_SUCCESS)
        {
            CFE_EVS_SendEvent(SAMPLE_APP_TABLE_REG_ERR_EID, CFE_EVS_EventType_ERROR,
                              "Sample App: Error Registering Example Table, RC = 0x%08lX", (unsigned long)status);
        }
        else
        {
            status = CFE_TBL_Load(SAMPLE_APP_Data.TblHandles[0], CFE_TBL_SRC_FILE, SAMPLE_APP_TABLE_FILE);
        }

        CFE_Config_GetVersionString(VersionString, SAMPLE_APP_CFG_MAX_VERSION_STR_LEN, "Sample App",
                                    SAMPLE_APP_VERSION, SAMPLE_APP_BUILD_CODENAME, SAMPLE_APP_LAST_OFFICIAL);

        CFE_EVS_SendEvent(SAMPLE_APP_INIT_INF_EID, CFE_EVS_EventType_INFORMATION, "Sample App Initialized.%s",
                          VersionString);
    }

    return status;
}


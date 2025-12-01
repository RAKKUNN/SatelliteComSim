#ifndef _sample_app_msg_h_
#define _sample_app_msg_h_

#include "cfe.h"
#include "cfe_sb.h"

/*
** SAMPLE App command codes
*/
#define SAMPLE_APP_NOOP_CC           0
#define SAMPLE_APP_RESET_COUNTERS_CC 1
#define SAMPLE_APP_PROCESS_CC        2
#define SAMPLE_APP_SEND_TEXT_CC      3

/* 텍스트 최대 길이 */
#define SAMPLE_APP_TEXT_MAX_LEN      128

/* No-Args 공통 명령 (msg.h에서 직접 정의) */
typedef struct
{
    CFE_SB_CmdHdr_t CmdHeader;
} SAMPLE_NoArgsCmd_t;

/* SEND_TEXT 명령: "ID:메시지" ASCII, 0 패딩 */
typedef struct
{
    CFE_SB_CmdHdr_t CmdHeader;
    char            Text[SAMPLE_APP_TEXT_MAX_LEN];
} SAMPLE_SendTextCmd_t;

/* 별칭 */
typedef SAMPLE_NoArgsCmd_t SAMPLE_Noop_t;
typedef SAMPLE_NoArgsCmd_t SAMPLE_ResetCounters_t;
typedef SAMPLE_NoArgsCmd_t SAMPLE_Process_t;

/* Housekeeping Telemetry (기존과 동일) */
typedef struct
{
    uint8 CommandErrorCounter;
    uint8 CommandCounter;
    uint8 spare[2];
} SAMPLE_HkTlm_Payload_t;

typedef struct
{
    uint8                 TlmHeader[CFE_SB_TLM_HDR_SIZE];
    SAMPLE_HkTlm_Payload_t  Payload;
} OS_PACK SAMPLE_HkTlm_t;

/* Text Telemetry (지상 에코) 
   → 첫 필드를 바이트 배열 헤더로 정의(예제 스타일) */
typedef struct
{
    uint8  MsgHdr[CFE_SB_TLM_HDR_SIZE];
    uint16 TextLen;
    char   Text[SAMPLE_APP_TEXT_MAX_LEN];
} SAMPLE_TextTlm_t;

#endif /* _sample_app_msg_h_ */


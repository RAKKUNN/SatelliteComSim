void SAMPLE_APP_ProcessGroundCommand(const CFE_SB_Buffer_t *SBBufPtr)
{
    CFE_MSG_FcnCode_t CommandCode = 0;

    CFE_MSG_GetFcnCode(&SBBufPtr->Msg, &CommandCode);

    switch (CommandCode)
    {
        case SAMPLE_APP_NOOP_CC:
            if (SAMPLE_APP_VerifyCmdLength(&SBBufPtr->Msg, sizeof(SAMPLE_APP_NoopCmd_t)))
            {
                SAMPLE_APP_NoopCmd((const SAMPLE_APP_NoopCmd_t *)SBBufPtr);
            }
            break;

        case SAMPLE_APP_RESET_COUNTERS_CC:
            if (SAMPLE_APP_VerifyCmdLength(&SBBufPtr->Msg, sizeof(SAMPLE_APP_ResetCountersCmd_t)))
            {
                SAMPLE_APP_ResetCountersCmd((const SAMPLE_APP_ResetCountersCmd_t *)SBBufPtr);
            }
            break;

        case SAMPLE_APP_PROCESS_CC:
            if (SAMPLE_APP_VerifyCmdLength(&SBBufPtr->Msg, sizeof(SAMPLE_APP_ProcessCmd_t)))
            {
                SAMPLE_APP_ProcessCmd((const SAMPLE_APP_ProcessCmd_t *)SBBufPtr);
            }
            break;

        case SAMPLE_APP_DISPLAY_PARAM_CC:
            if (SAMPLE_APP_VerifyCmdLength(&SBBufPtr->Msg, sizeof(SAMPLE_APP_DisplayParamCmd_t)))
            {
                SAMPLE_APP_DisplayParamCmd((const SAMPLE_APP_DisplayParamCmd_t *)SBBufPtr);
            }
            break;

        case SAMPLE_SEND_TEXT_CC:
            if (SAMPLE_APP_VerifyCmdLength(&SBBufPtr->Msg, sizeof(SAMPLE_SendTextCmd_t)))
            {
                SAMPLE_SendText((const SAMPLE_SendTextCmd_t *)SBBufPtr);
            }
            break;

        default:
            CFE_EVS_SendEvent(SAMPLE_APP_CC_ERR_EID, CFE_EVS_EventType_ERROR, "Invalid ground command code: CC = %d",
                              CommandCode);
            break;
    }
}


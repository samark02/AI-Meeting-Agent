let isRecording = false;
let currentRecordingData = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.action) {
        case 'START_RECORDING':
            isRecording = true;
            currentRecordingData = message.recordingData;
            sendResponse({ status: 'started' });
            return true;
        case 'STOP_RECORDING':
            isRecording = false;
            currentRecordingData = null;
            sendResponse({ status: 'stopped' });
            return true;
        case 'GET_RECORDING_STATE':
            sendResponse({ 
                isRecording,
                recordingData: currentRecordingData 
            });
            return true;
    }
});
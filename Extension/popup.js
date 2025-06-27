document.addEventListener('DOMContentLoaded', function() {
    const recordButton = document.getElementById('recordButton');
    const timerDisplay = document.getElementById('timer');
    const status = document.getElementById('status');
    const clientNameInput = document.getElementById('clientName');
    const clientNameError = document.getElementById('clientNameError');

    // Chatbot variables
    const chatMessages = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');

    let mediaRecorder = null;
    let audioChunks = [];
    let startTime = null;
    let timerInterval = null;
    let audioContext = null;
    let recordingStartTime = null;
    let recordingEndTime = null;

    // Check if recording is already in progress when popup opens
    chrome.runtime.sendMessage({ action: 'GET_RECORDING_STATE' }, function(response) {
        if (response.isRecording) {
            recordButton.textContent = 'Stop Recording';
            recordButton.classList.add('recording');
            clientNameInput.value = response.recordingData.clientName;
            clientNameInput.disabled = true;
            status.textContent = 'Recording...';
            
            // Restore recording state
            startTime = response.recordingData.startTime;
            recordingStartTime = new Date(startTime);
            updateTimer();
            timerInterval = setInterval(updateTimer, 1000);

            // Restart media recording
            initializeRecording();
        }
    });

    // Validate client name
    function validateClientName() {
        const clientName = clientNameInput.value.trim();
        if (!clientName) {
            clientNameError.style.display = 'block';
            return false;
        }
        clientNameError.style.display = 'none';
        return true;
    }

    // Update timer
    function updateTimer() {
        if (!startTime) return;
        const endTime = recordingEndTime || new Date().getTime();
        const elapsed = endTime - startTime;
        const seconds = Math.floor((elapsed / 1000) % 60);
        const minutes = Math.floor((elapsed / 1000) / 60);
        timerDisplay.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    // Calculate recording duration
    function calculateDuration(startMs, endMs) {
        const durationMs = endMs - startMs;
        const minutes = Math.floor(durationMs / 60000);
        const seconds = ((durationMs % 60000) / 1000).toFixed(0);
        return `${minutes}m${seconds}s`;
    }

    // Format date and time
    function formatDateTime(date) {
        if (!(date instanceof Date)) {
            date = new Date(date);
        }
        
        const formattedDate = `${date.getDate().toString().padStart(2, '0')}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getFullYear()}`;
        const formattedTime = `${date.getHours().toString().padStart(2, '0')}-${date.getMinutes().toString().padStart(2, '0')}`;
        
        return {
            date: formattedDate,
            time: formattedTime,
            full: `${formattedDate}_${formattedTime}`
        };
    }

    // Generate file path for audio
    function generateFilePath(metadata) {
        const { clientName, startDateTime, duration } = metadata;
        return {
            folderPath: `${clientName}/${startDateTime.date}`,
            // fileName: `${clientName}_${startDateTime.time}_${duration}.wav`,
            fileName: `audio.wav`,
            fullPath: `${clientName}/${startDateTime.date}/audio/audio.wav`
            // fullPath: `${clientName}/${startDateTime.date}/audio/${clientName}_${startDateTime.time}_${duration}.wav`
        };
    }

    // Upload audio to cloud
    async function uploadToCloud(audioBlob, metadata, retryCount = 3) {
        const paths = generateFilePath(metadata);
        const formData = new FormData();
        
        const maxChunkSize = 1024 * 1024; // 1MB chunks
        const chunks = Math.ceil(audioBlob.size / maxChunkSize);
        
        formData.append('audio', audioBlob);
        formData.append('clientName', metadata.clientName);
        formData.append('metadata', JSON.stringify({
            ...metadata,
            filePath: paths.fullPath,
            fileName: paths.fileName,
            folderPath : paths.folderPath,
            totalChunks: chunks
        }));

        for (let attempt = 1; attempt <= retryCount; attempt++) {
            try {
                status.textContent = `Uploading to server (attempt ${attempt}/${retryCount})...`;
                
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000);

                const response = await fetch('https://happy-topical-jaybird.ngrok-free.app/notter/upload-audio', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                }

                const result = await response.json();
                status.textContent = 'Recording uploaded successfully.';
                return result;

            } catch (error) {
                console.error(`Upload attempt ${attempt} failed:`, error);
                if (attempt === retryCount) {
                    status.textContent = `Upload failed after ${retryCount} attempts: ${error.message}`;
                    throw error;
                }
                await new Promise(resolve => setTimeout(resolve, Math.min(1000 * Math.pow(2, attempt), 5000)));
            }
        }
    }

    // Initialize audio context
    async function setupAudioContext(tabStream) {
        audioContext = new AudioContext();
        const tabSource = audioContext.createMediaStreamSource(tabStream);
        const mixer = audioContext.createGain();
        mixer.gain.value = 1.0;

        // Tab audio processing
        const tabCompressor = audioContext.createDynamicsCompressor();
        tabCompressor.threshold.value = -50;
        tabCompressor.knee.value = 40;
        tabCompressor.ratio.value = 12;
        tabCompressor.attack.value = 0;
        tabCompressor.release.value = 0.25;

        tabSource.connect(tabCompressor);
        tabCompressor.connect(mixer);

        // Tab audio playback
        const tabPlaybackGain = audioContext.createGain();
        tabPlaybackGain.gain.value = 1.0;
        tabSource.connect(tabPlaybackGain);
        tabPlaybackGain.connect(audioContext.destination);

        // Try to get microphone access with better error handling
        let micStream = null;
        try {
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: false
                }
            }).catch(error => {
                if (error.name === 'NotAllowedError') {
                    console.warn('Microphone access denied by user');
                } else if (error.name === 'NotFoundError') {
                    console.warn('No microphone found');
                } else {
                    console.warn('Microphone error:', error.message);
                }
                return null;
            });

            if (micStream) {
                const micSource = audioContext.createMediaStreamSource(micStream);
                const micCompressor = audioContext.createDynamicsCompressor();
                micCompressor.threshold.value = -50;
                micCompressor.knee.value = 40;
                micCompressor.ratio.value = 12;
                micCompressor.attack.value = 0;
                micCompressor.release.value = 0.25;

                const micGain = audioContext.createGain();
                micGain.gain.value = 1.5;

                micSource.connect(micGain);
                micGain.connect(micCompressor);
                micCompressor.connect(mixer);
            }
        } catch (error) {
            console.warn('Failed to initialize microphone:', error);
        }

        const destination = audioContext.createMediaStreamDestination();
        mixer.connect(destination);

        return {
            stream: destination.stream,
            cleanup: () => {
                if (micStream) {
                    micStream.getTracks().forEach(track => track.stop());
                }
                if (tabStream) {
                    tabStream.getTracks().forEach(track => track.stop());
                }
            }
        };
    }

    // Initialize recording
    async function initializeRecording() {
        try {
            chrome.tabCapture.capture({
                audio: true,
                video: false
            }, async function(stream) {
                if (!stream) {
                    throw new Error('Failed to capture tab audio');
                }

                try {
                    const audio = new Audio();
                    audio.srcObject = stream;
                    await audio.play();

                    const { stream: mixedStream, cleanup } = await setupAudioContext(stream);

                    mediaRecorder = new MediaRecorder(mixedStream, {
                        mimeType: 'audio/webm;codecs=opus',
                        audioBitsPerSecond: 128000
                    });

                    audioChunks = [];

                    mediaRecorder.ondataavailable = function(event) {
                        if (event.data.size > 0) {
                            audioChunks.push(event.data);
                        }
                    };

                    mediaRecorder.onstop = async function() {
                        cleanup();
                        audio.pause();
                        audio.srcObject = null;

                        recordingEndTime = new Date();
                        updateTimer();

                        const duration = calculateDuration(recordingStartTime.getTime(), recordingEndTime.getTime());
                        const startDateTime = formatDateTime(recordingStartTime);

                        const metadata = {
                            clientName: clientNameInput.value.trim(),
                            startDateTime,
                            duration,
                            recordingStartTime: recordingStartTime.toISOString(),
                            recordingEndTime: recordingEndTime.toISOString()
                        };

                        const audioBlob = new Blob(audioChunks, {
                            type: 'audio/webm;codecs=opus'
                        });

                        try {
                            await uploadToCloud(audioBlob, metadata);
                        } catch (error) {
                            console.error('Final upload attempt failed:', error);
                        }

                        // Cleanup
                        if (audioContext) {
                            audioContext.close();
                            audioContext = null;
                        }

                        // Notify background that recording has stopped
                        chrome.runtime.sendMessage({ action: 'STOP_RECORDING' });

                        stream.getTracks().forEach(track => track.stop());
                        recordButton.textContent = 'Start Recording';
                        recordButton.classList.remove('recording');
                        clearInterval(timerInterval);
                        startTime = null;
                        clientNameInput.disabled = false;
                    };

                    mediaRecorder.start(1000);
                    
                    // Store recording state in background
                    chrome.runtime.sendMessage({
                        action: 'START_RECORDING',
                        recordingData: {
                            clientName: clientNameInput.value.trim(),
                            startTime: startTime,
                            recordingStartTime: recordingStartTime.toISOString()
                        }
                    });

                } catch (error) {
                    console.error('Error during recording setup:', error);
                    status.textContent = 'Error: ' + error.message;
                    clientNameInput.disabled = false;
                    if (stream) {
                        stream.getTracks().forEach(track => track.stop());
                    }
                }
            });
        } catch (error) {
            console.error('Error starting recording:', error);
            status.textContent = 'Error: ' + error.message;
            clientNameInput.disabled = false;
        }
    }

    // Start recording
    async function startRecording() {
        if (!validateClientName()) {
            return;
        }

        clientNameInput.disabled = true;
        status.textContent = 'Initializing...';
        recordingEndTime = null;
        recordingStartTime = new Date();
        startTime = recordingStartTime.getTime();
        
        timerInterval = setInterval(updateTimer, 1000);
        status.textContent = 'Recording...';
        recordButton.textContent = 'Stop Recording';
        recordButton.classList.add('recording');

        await initializeRecording();
    }

    // Stop recording
    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
    }

    // Chatbot message sending functionality
    function sendChatMessage() {
        const message = chatInput.value.trim();
        if (message) {
            // Add user message to chat
            chatMessages.innerHTML += `<div class="user-message">${message}</div>`;
            chatInput.value = '';

            // Show typing indicator (if applicable)
            // showTypingIndicator();

            try {
                // Prepare JSON data to send to the server
                const requestData = {
                    message: message,
                    conversation_id: "test1" // Assuming conversationId is available
                };

                // Send the POST request to the chatbot API
                const response = fetch('https://happy-topical-jaybird.ngrok-free.app/notter/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestData)
                })
                .then(response => response.text()) // Use .text() to get the string response
                .then(responseText => {
                    console.log(responseText); // The response is a plain string
                    chatMessages.innerHTML += `<div class="chatbot-message">${responseText}</div>`;
                })
                .catch(error => {
                    console.error('Error:', error);
                });

                // console.log("Response: ",response);

                // Parse the JSON response from the server
                // const data = JSON.parse(response);

                // Hide typing indicator
                // hideTypingIndicator();

                // if (data.error) {
                    // If there's an error in the response
                // chatMessages.innerHTML += `<div class="chatbot-message">Sorry, there was an error processing your request.</div>`;
                // } else {
                    // If the response is successful, display the chatbot's message
                // chatMessages.innerHTML += `<div class="chatbot-message">Bot: ${response.text()}</div>`;
                // }

                // Scroll to the bottom of the chat
                chatMessages.scrollTop = chatMessages.scrollHeight;

            } catch (error) {
                // If there's a network or connection error
                // hideTypingIndicator();
                chatMessages.innerHTML += `<div class="chatbot-message">Sorry, there was an error connecting to the server.</div>`;
                console.error('Error:', error);
            }
        }
    }

    sendButton.addEventListener('click', sendChatMessage);
    chatInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            sendChatMessage();
        }
    });

    // Record button functionality
    recordButton.addEventListener('click', () => {
        if (recordButton.classList.contains('recording')) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    document.getElementById('dashboardButton').addEventListener('click', function() {
        window.open('https://huggingface.co/spaces/ArunK-2003/KapNotes', '_blank');
    });
});

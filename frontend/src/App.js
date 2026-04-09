import React, { useState, useRef, useEffect } from 'react';
import './App.css';

function App() {
  // Combined state management
  const [activeModules, setActiveModules] = useState({
    video: false,
    audio: false
  });
  const [combinedScore, setCombinedScore] = useState(null);

  // Video analysis state
  const [videoState, setVideoState] = useState({
    isAnalyzing: false,
    sessionId: '',
    emotionData: [],
    dominantEmotion: null,
    averageScore: 0,
    error: null,
    isLoading: false
  });

  // Audio analysis state
  const [audioState, setAudioState] = useState({
    isRecording: false,
    conversation: [],
    sessionId: '',
    isLoading: false,
    summary: null,
    error: null,
    latitude: null,
    longitude: null
  });

  // Refs for both modules
  const videoRefs = {
    ws: useRef(null),
    videoRef: useRef(null),
    streamRef: useRef(null),
    canvasRef: useRef(null),
    frameInterval: useRef(null)
  };
  const audioRefs = {
    ws: useRef(null),
    mediaRecorder: useRef(null),
    audioContext: useRef(null)
  };

  // Helper functions for video module
  const initializeVideoSession = () => {
    try {
      const newSessionId = `video-session-${Date.now()}`;
      setVideoState(prev => ({
        ...prev,
        sessionId: newSessionId,
        error: null,
        isLoading: true
      }));
      videoRefs.ws.current = new WebSocket(
        `ws://${window.location.hostname}:8000/api/video/ws/video/${newSessionId}`
      );
      videoRefs.ws.current.onopen = () => {
        setVideoState(prev => ({ ...prev, isLoading: false }));
      };
      videoRefs.ws.current.onerror = (err) => {
        setVideoState(prev => ({
          ...prev,
          error: 'Failed to connect to video analysis server',
          isLoading: false
        }));
        console.error('Video WebSocket error:', err);
      };
      videoRefs.ws.current.onclose = () => {
        console.log('Video WebSocket disconnected');
      };
      videoRefs.ws.current.onmessage = handleVideoWebSocketMessage;
    } catch (err) {
      setVideoState(prev => ({
        ...prev,
        error: 'Failed to initialize video session',
        isLoading: false
      }));
      console.error('Video initialization error:', err);
    }
  };

  const handleVideoWebSocketMessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (!data || !data.type) return;
      switch (data.type) {
        case 'analysis':
          updateVideoEmotionData(data);
          break;
        case 'error':
          setVideoState(prev => ({
            ...prev,
            error: data.message || 'Video server error occurred'
          }));
          break;
        default:
          console.warn('Unknown video message type:', data.type);
      }
    } catch (err) {
      console.error('Error processing video message:', err);
    }
  };

  const updateVideoEmotionData = (data) => {
    setVideoState(prev => {
      const newData = [...prev.emotionData, {
        emotion: data.emotion,
        score: data.score,
        timestamp: data.timestamp
      }];
      const emotionCounts = {};
      let totalScore = 0;
      newData.forEach(item => {
        emotionCounts[item.emotion] = (emotionCounts[item.emotion] || 0) + 1;
        totalScore += item.score;
      });
      const dominantEmotion = Object.keys(emotionCounts).reduce((a, b) =>
        emotionCounts[a] > emotionCounts[b] ? a : b
      );
      const averageScore = totalScore / newData.length;
      return { ...prev, emotionData: newData, dominantEmotion, averageScore };
    });
  };

  const startVideoAnalysis = async () => {
    if (videoState.isAnalyzing || !videoRefs.videoRef.current) return;
    setVideoState(prev => ({ ...prev, error: null, isLoading: true }));
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false
      });
      videoRefs.streamRef.current = stream;
      if (videoRefs.videoRef.current) {
        videoRefs.videoRef.current.srcObject = stream;
      }
      videoRefs.frameInterval.current = setInterval(() => {
        captureVideoFrame();
      }, 1000);
      setVideoState(prev => ({ ...prev, isAnalyzing: true, isLoading: false }));
    } catch (err) {
      setVideoState(prev => ({
        ...prev,
        error: err.message.includes('permission') ?
          'Camera access was denied. Please enable camera permissions.' :
          'Failed to access camera. Please check your device.',
        isAnalyzing: false,
        isLoading: false
      }));
      console.error('Camera access error:', err);
    }
  };

  const stopVideoAnalysis = () => {
    if (!videoState.isAnalyzing) return;
    cleanupVideoResources();
    setVideoState(prev => ({ ...prev, isAnalyzing: false }));
  };

  const cleanupVideoResources = () => {
    if (videoRefs.frameInterval.current) {
      clearInterval(videoRefs.frameInterval.current);
      videoRefs.frameInterval.current = null;
    }
    if (videoRefs.streamRef.current) {
      videoRefs.streamRef.current.getTracks().forEach(track => track.stop());
      videoRefs.streamRef.current = null;
    }
    if (videoRefs.videoRef.current && videoRefs.videoRef.current.srcObject) {
      videoRefs.videoRef.current.srcObject = null;
    }
    if (videoRefs.ws.current && videoRefs.ws.current.readyState === WebSocket.OPEN) {
      videoRefs.ws.current.close();
    }
  };

  const captureVideoFrame = () => {
    try {
      if (!videoRefs.videoRef.current ||
          !videoRefs.canvasRef.current ||
          !videoRefs.videoRef.current.videoWidth ||
          !videoRefs.videoRef.current.videoHeight) return;

      const video = videoRefs.videoRef.current;
      const canvas = videoRefs.canvasRef.current;
      if (video.readyState !== 4) return;

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(blob => {
        if (!blob || !videoRefs.ws.current || videoRefs.ws.current.readyState !== WebSocket.OPEN) return;
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const base64Data = reader.result.split(',')[1];
            const binaryString = atob(base64Data);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              bytes[i] = binaryString.charCodeAt(i);
            }
            videoRefs.ws.current.send(bytes.buffer);
          } catch (err) {
            console.error('Error sending video frame:', err);
          }
        };
        reader.readAsDataURL(blob);
      }, 'image/jpeg', 0.8);
    } catch (err) {
      console.error('Video frame capture error:', err);
    }
  };

  // Helper functions for audio module
  const getWavBytes = (buffer, options) => {
    const numFrames = buffer.length;
    const numChannels = options.numChannels || 1;
    const sampleRate = options.sampleRate || 16000;
    const bytesPerSample = options.isFloat ? 4 : 2;
    const format = options.isFloat ? 3 : 1;
    const blockAlign = numChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = numFrames * blockAlign;
    const bufferSize = 44 + dataSize;
    const buf = new ArrayBuffer(bufferSize);
    const view = new DataView(buf);
    const writeString = (view, offset, string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, format, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bytesPerSample * 8, true);
    writeString(view, 36, 'data');
    view.setUint32(40, dataSize, true);
    const volume = 1;
    let offset = 44;
    for (let i = 0; i < buffer.length; i++) {
      view.setInt16(offset, buffer[i] * (0x7FFF * volume), true);
      offset += 2;
    }
    return buf;
  };

  const playAudioResponse = (base64Audio) => {
    const audio = new Audio(`data:audio/wav;base64,${base64Audio}`);
    audio.play();
  };

  const initializeAudioSession = () => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => setAudioState(prev => ({ ...prev, latitude: position.coords.latitude, longitude: position.coords.longitude })),
        (error) => console.log("Location access denied or error:", error)
      );
    }
    const newSessionId = 'audio-session-' + Date.now();
    setAudioState(prev => ({ ...prev, sessionId: newSessionId }));
    audioRefs.audioContext.current = new (window.AudioContext || window.webkitAudioContext)();
    audioRefs.ws.current = new WebSocket(
      `ws://${window.location.hostname}:8000/api/voice/ws/conversation/${newSessionId}`
    );
    audioRefs.ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'ai_response') {
        setAudioState(prev => ({
          ...prev,
          isLoading: false,
          conversation: [
            ...prev.conversation,
            {
              speaker: 'bot',
              text: data.text_response || "No response generated",
              confidence: data.confidence_score,
              isDepressed: data.is_depressed,
              helplines: data.helplines || []
            }
          ]
        }));
        if (data.audio_response) {
          playAudioResponse(data.audio_response);
        }
      } else if (data.type === 'transcription_failed' || data.type === 'error') {
        setAudioState(prev => ({
          ...prev,
          isLoading: false,
          error: data.message || 'Error communicating with analysis server'
        }));
        console.error('Audio WebSocket message error:', data.message);
      }
    };
    audioRefs.ws.current.onerror = (err) => {
      setAudioState(prev => ({ ...prev, error: 'Failed to connect to audio analysis server' }));
      console.error('Audio WebSocket error:', err);
    };
  };

  const startAudioRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });
      setAudioState(prev => ({ ...prev, isRecording: true }));
      audioRefs.mediaRecorder.current = new MediaRecorder(stream, {
        mimeType: 'audio/webm',
        audioBitsPerSecond: 128000
      });
      const audioChunks = [];
      audioRefs.mediaRecorder.current.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };
      audioRefs.mediaRecorder.current.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        await processAudio(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };
      audioRefs.mediaRecorder.current.start(500);
    } catch (err) {
      console.error('Audio recording error:', err);
      setAudioState(prev => ({
        ...prev,
        isRecording: false,
        error: err.message.includes('permission') ?
          'Microphone access was denied. Please enable microphone permissions.' :
          'Failed to access microphone. Please check your device.'
      }));
    }
  };

  const stopAudioRecording = () => {
    if (audioRefs.mediaRecorder.current && audioState.isRecording) {
      audioRefs.mediaRecorder.current.stop();
      setAudioState(prev => ({ ...prev, isRecording: false, isLoading: true }));
    }
  };

  const processAudio = async (audioBlob) => {
    try {
      const wavBlob = await convertToWav(audioBlob);
      const reader = new FileReader();
      reader.onload = () => {
        const base64Audio = reader.result.split(',')[1];
        audioRefs.ws.current.send(JSON.stringify({
          type: "audio",
          audio: base64Audio,
          transcription: "",
          latitude: audioState.latitude,
          longitude: audioState.longitude
        }));
      };
      reader.readAsDataURL(wavBlob);
    } catch (err) {
      console.error('Audio processing error:', err);
      setAudioState(prev => ({ ...prev, isLoading: false, error: 'Failed to process audio' }));
    }
  };

  const convertToWav = async (blob) => {
    const arrayBuffer = await blob.arrayBuffer();
    const audioBuffer = await audioRefs.audioContext.current.decodeAudioData(arrayBuffer);
    const offlineCtx = new OfflineAudioContext(1, 16000 * audioBuffer.duration, 16000);
    const source = offlineCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offlineCtx.destination);
    source.start();
    const resampledBuffer = await offlineCtx.startRendering();
    const wavBytes = getWavBytes(resampledBuffer.getChannelData(0), {
      isFloat: false, numChannels: 1, sampleRate: 16000,
    });
    return new Blob([wavBytes], { type: 'audio/wav' });
  };

  const calculateAudioSummary = () => {
    const botMessages = audioState.conversation.filter(msg => msg.speaker === 'bot');
    if (botMessages.length === 0) {
      setAudioState(prev => ({ ...prev, summary: { averageConfidence: 0, totalMessages: 0, depressedCount: 0 } }));
      return;
    }
    const totalConfidence = botMessages.reduce((sum, msg) => sum + (msg.confidence || 0), 0);
    const depressedCount = botMessages.filter(msg => msg.isDepressed).length;
    setAudioState(prev => ({
      ...prev,
      summary: { averageConfidence: totalConfidence / botMessages.length, totalMessages: botMessages.length, depressedCount }
    }));
  };

  const calculateCombinedScore = () => {
    let videoScore = null;
    let audioScore = null;
    if (activeModules.video && videoState.emotionData.length > 0) videoScore = videoState.averageScore;
    if (activeModules.audio && audioState.summary?.totalMessages > 0) audioScore = audioState.summary.averageConfidence;
    if (videoScore !== null && audioScore !== null) return (videoScore + audioScore) / 2;
    else if (videoScore !== null) return videoScore;
    else if (audioScore !== null) return audioScore;
    else return null;
  };

  useEffect(() => {
    const newScore = calculateCombinedScore();
    setCombinedScore(newScore);
  }, [videoState.averageScore, audioState.summary, activeModules]);

  const toggleVideoModule = () => {
    const newState = !activeModules.video;
    setActiveModules(prev => ({ ...prev, video: newState }));
    if (newState) {
      initializeVideoSession();
    } else {
      if (videoState.isAnalyzing) stopVideoAnalysis();
      cleanupVideoResources();
      setVideoState(prev => ({ ...prev, emotionData: [], dominantEmotion: null, averageScore: 0 }));
    }
  };

  const toggleAudioModule = () => {
    const newState = !activeModules.audio;
    setActiveModules(prev => ({ ...prev, audio: newState }));
    if (newState) {
      initializeAudioSession();
    } else {
      if (audioState.isRecording) stopAudioRecording();
      if (audioRefs.ws.current && audioRefs.ws.current.readyState === WebSocket.OPEN) audioRefs.ws.current.close();
      if (audioRefs.audioContext.current.state !== 'closed') audioRefs.audioContext.current.close();
      setAudioState(prev => ({ ...prev, conversation: [], summary: null }));
    }
  };

  const getEmotionColor = (emotion) => {
    const colors = {
      happy: '#4CAF50', neutral: '#9E9E9E', sad: '#2196F3',
      angry: '#F44336', fear: '#673AB7', disgust: '#795548', surprise: '#FFC107'
    };
    return colors[emotion] || '#000000';
  };

  useEffect(() => {
    return () => {
      cleanupVideoResources();
      if (audioRefs.ws.current && audioRefs.ws.current.readyState === WebSocket.OPEN) audioRefs.ws.current.close();
      if (audioRefs.audioContext.current && audioRefs.audioContext.current.state !== 'closed') audioRefs.audioContext.current.close();
    };
  }, []);

  return (
    <div className="app-container">
      <h1>Multimodal Emotion Analysis Dashboard</h1>

      <div className="module-selector">
        <div className="module-toggle">
          <label>
            <input type="checkbox" checked={activeModules.video} onChange={toggleVideoModule} />
            Video Analysis
          </label>
        </div>
        <div className="module-toggle">
          <label>
            <input type="checkbox" checked={activeModules.audio} onChange={toggleAudioModule} />
            Audio Conversation
          </label>
        </div>
      </div>

      {videoState.error && (
        <div className="error-message video-error">
          <strong>Video Error:</strong> {videoState.error}
          <button onClick={() => setVideoState(prev => ({ ...prev, error: null }))} className="dismiss-button">×</button>
        </div>
      )}

      {audioState.error && (
        <div className="error-message audio-error">
          <strong>Audio Error:</strong> {audioState.error}
          <button onClick={() => setAudioState(prev => ({ ...prev, error: null }))} className="dismiss-button">×</button>
        </div>
      )}

      {(videoState.isLoading || audioState.isLoading) && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <p>Processing...</p>
        </div>
      )}

      <div className="dashboard-content">
        {activeModules.video && (
          <div className="module-container video-module">
            <h2>Video Emotion Analysis</h2>
            <div className="video-container">
              <video ref={videoRefs.videoRef} autoPlay playsInline muted
                style={{ display: videoState.isAnalyzing ? 'block' : 'none' }} />
              {!videoState.isAnalyzing && (
                <div className="video-placeholder">
                  {videoState.isLoading ? 'Initializing...' : 'Camera will appear here when analysis starts'}
                </div>
              )}
            </div>
            <canvas ref={videoRefs.canvasRef} style={{ display: 'none' }} />
            <div className="controls">
              <button
                onClick={videoState.isAnalyzing ? stopVideoAnalysis : startVideoAnalysis}
                className={`control-button ${videoState.isAnalyzing ? 'stop-button' : 'start-button'}`}
                disabled={videoState.isLoading || !activeModules.video}
              >
                {videoState.isAnalyzing ? 'Stop Analysis' : 'Start Analysis'}
              </button>
            </div>
            <div className="analysis-results">
              <h3>Real-time Video Analysis</h3>
              {videoState.emotionData.length > 0 ? (
                <>
                  <div className="summary">
                    <p><strong>Dominant Emotion:</strong>
                      <span style={{ color: getEmotionColor(videoState.dominantEmotion) }}>
                        {videoState.dominantEmotion}
                      </span>
                    </p>
                    <p><strong>Average Score:</strong> {videoState.averageScore.toFixed(2)}</p>
                    <p><strong>Frames Analyzed:</strong> {videoState.emotionData.length}</p>
                  </div>
                  <div className="emotion-chart-container">
                    <div className="emotion-chart">
                      {videoState.emotionData.slice().reverse().map((item, index) => (
                        <div key={index} className="emotion-bar"
                          style={{ height: `${item.score * 100}%`, backgroundColor: getEmotionColor(item.emotion) }}>
                          <span className="emotion-label">{item.emotion}</span>
                          <span className="emotion-score">{item.score.toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <p className="no-data-message">No video analysis data yet. Start the video analysis to see results.</p>
              )}
            </div>
          </div>
        )}

        {activeModules.audio && (
          <div className="module-container audio-module">
            <h2>Audio Conversation Analysis</h2>
            <div className="status">
              {audioState.isRecording ? (
                <div className="recording-indicator">
                  <div className="pulse-circle"></div>
                  Recording...
                </div>
              ) : (
                <div>Ready to record</div>
              )}
            </div>
            <div className="controls">
              <button
                onClick={audioState.isRecording ? stopAudioRecording : startAudioRecording}
                className={`control-button ${audioState.isRecording ? 'stop-button' : 'start-button'}`}
                disabled={audioState.isLoading || !activeModules.audio}
              >
                {audioState.isRecording ? 'Stop Recording' : 'Start Recording'}
              </button>
              <button onClick={calculateAudioSummary} className="control-button results-button"
                disabled={audioState.conversation.length === 0 || audioState.isLoading}>
                Get Audio Summary
              </button>
            </div>
            {audioState.summary && (
              <div className="summary-box">
                <h3>Conversation Summary</h3>
                <p><strong>Total Messages:</strong> {audioState.summary.totalMessages}</p>
                <p><strong>Average Confidence:</strong> {(audioState.summary.averageConfidence * 100).toFixed(1)}%</p>
                <p><strong>Depression Detections:</strong> {audioState.summary.depressedCount}</p>
              </div>
            )}
            <div className="conversation-log">
              {audioState.conversation.map((msg, i) => (
                <div key={i} className={`message ${msg.speaker}`}>
                  <div className="message-header">
                    <strong>{msg.speaker === 'user' ? 'You' : 'Therapist'}</strong>
                    {msg.confidence !== undefined && (
                      <span className="confidence-score">Confidence: {(msg.confidence * 100).toFixed(0)}%</span>
                    )}
                  </div>
                  <div className="message-content">{msg.text || <em>No text response</em>}</div>
                  {msg.helplines && msg.helplines.length > 0 && (
                    <div className="helpline-card" style={{ border: '2px solid #F44336', borderRadius: '8px', padding: '10px', marginTop: '10px', backgroundColor: '#ffeaea' }}>
                      <h4 style={{ color: '#F44336', margin: '0 0 8px 0', display: 'flex', alignItems: 'center' }}>
                        <span style={{ marginRight: '8px' }}>🆘</span> Helplines Near You
                      </h4>
                      <ol style={{ margin: 0, paddingLeft: '20px', color: '#B71C1C' }}>
                        {msg.helplines.map((hl, index) => (
                          <li key={index}><strong>{hl.name}</strong> — {hl.number}</li>
                        ))}
                      </ol>
                    </div>
                  )}
                </div>
              ))}
              {audioState.isLoading && <div className="message bot">Processing...</div>}
            </div>
          </div>
        )}
      </div>

      {combinedScore !== null && (
        <div className="combined-score-display">
          <h3>Depression Likelihood Score</h3>
          <div className="score-bar">
            <div className="score-fill" style={{ width: `${combinedScore * 100}%` }}>
              {(combinedScore * 100).toFixed(1)}%
            </div>
          </div>
          <p className="score-description">
            {combinedScore < 0.3 ? 'Low likelihood of depression' :
             combinedScore < 0.6 ? 'Moderate likelihood of depression' :
             'High likelihood of depression'}
          </p>
        </div>
      )}
    </div>
  );
}

export default App;

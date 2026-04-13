import React, { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useMaybeRoomContext
} from '@livekit/components-react';
import '@livekit/components-styles';
import { ConnectionState, RoomEvent } from 'livekit-client';

const API_BASE = `http://${window.location.hostname}:8000`;

function App() {
  const [activeModules, setActiveModules] = useState({ video: true, audio: true });
  const [combinedScore, setCombinedScore] = useState(null);

  // Voice analysis aggregated data (fed from the child ActiveVoiceSession)
  const [voiceAnalysisData, setVoiceAnalysisData] = useState({
    averageConfidence: 0,
    messages: [],        // [{text, isAgent, confidence, severity, is_depressed, needs_professional_help, timestamp}]
  });

  // Video analysis state
  const [videoState, setVideoState] = useState({
    isAnalyzing: false, sessionId: '', emotionData: [], dominantEmotion: null, averageScore: 0, error: null, isLoading: false
  });

  const videoRefs = { ws: useRef(null), videoRef: useRef(null), streamRef: useRef(null), canvasRef: useRef(null), frameInterval: useRef(null) };

  // Session state
  const [sessionStartTime, setSessionStartTime] = useState(null);
  const [showReportModal, setShowReportModal] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);

  const initializeVideoSession = () => {
    try {
      const newSessionId = `video-session-${Date.now()}`;
      setVideoState(prev => ({ ...prev, sessionId: newSessionId, error: null, isLoading: true }));
      videoRefs.ws.current = new WebSocket(`ws://${window.location.hostname}:8000/api/video/ws/video/${newSessionId}`);
      videoRefs.ws.current.onopen = () => setVideoState(prev => ({ ...prev, isLoading: false }));
      videoRefs.ws.current.onerror = (err) => {
        setVideoState(prev => ({ ...prev, error: 'Failed to connect to video server', isLoading: false }));
      };
      videoRefs.ws.current.onmessage = handleVideoWebSocketMessage;
    } catch (err) {
      setVideoState(prev => ({ ...prev, error: 'Failed to initialize video', isLoading: false }));
    }
  };

  const handleVideoWebSocketMessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'analysis') updateVideoEmotionData(data);
    } catch (err) { }
  };

  const updateVideoEmotionData = (data) => {
    setVideoState(prev => {
      const newData = [...prev.emotionData, { emotion: data.emotion, score: data.score, timestamp: data.timestamp }];
      const emotionCounts = {}; let totalScore = 0;
      newData.forEach(item => {
        emotionCounts[item.emotion] = (emotionCounts[item.emotion] || 0) + 1;
        totalScore += item.score;
      });
      const dominantEmotion = Object.keys(emotionCounts).reduce((a, b) => emotionCounts[a] > emotionCounts[b] ? a : b);
      return { ...prev, emotionData: newData, dominantEmotion, averageScore: totalScore / newData.length };
    });
  };

  const startVideoAnalysis = async () => {
    if (videoState.isAnalyzing) return;
    setVideoState(prev => ({ ...prev, error: null, isLoading: true }));
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { ideal: 640, height: 480, facingMode: 'user' }, audio: false });
      videoRefs.streamRef.current = stream;
      if (videoRefs.videoRef.current) videoRefs.videoRef.current.srcObject = stream;

      if (!videoRefs.ws.current || videoRefs.ws.current.readyState !== WebSocket.OPEN) {
        initializeVideoSession();
      }

      videoRefs.frameInterval.current = setInterval(() => captureVideoFrame(), 1000);
      setVideoState(prev => ({ ...prev, isAnalyzing: true, isLoading: false }));
    } catch (err) {
      setVideoState(prev => ({ ...prev, error: 'Camera access denied', isAnalyzing: false, isLoading: false }));
    }
  };

  const stopVideoAnalysis = () => {
    if (videoRefs.frameInterval.current) clearInterval(videoRefs.frameInterval.current);
    if (videoRefs.streamRef.current) videoRefs.streamRef.current.getTracks().forEach(track => track.stop());
    if (videoRefs.videoRef.current) videoRefs.videoRef.current.srcObject = null;
    setVideoState(prev => ({ ...prev, isAnalyzing: false }));
  };

  const captureVideoFrame = () => {
    try {
      const video = videoRefs.videoRef.current; const canvas = videoRefs.canvasRef.current;
      if (!video || !canvas || video.readyState !== 4) return;
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(blob => {
        if (!blob || !videoRefs.ws.current || videoRefs.ws.current.readyState !== WebSocket.OPEN) return;
        const reader = new FileReader();
        reader.onload = () => {
          const binaryString = atob(reader.result.split(',')[1]);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i);
          videoRefs.ws.current.send(bytes.buffer);
        };
        reader.readAsDataURL(blob);
      }, 'image/jpeg', 0.8);
    } catch (err) { }
  };

  // Combined score: 0.7 × voice + 0.3 × facial  (or the available modality alone)
  const calculateCombinedScore = useCallback(() => {
    const hasVoice = voiceAnalysisData.messages.length > 0;
    const hasFacial = videoState.emotionData.length > 0;

    if (hasVoice && hasFacial) {
      return 0.7 * voiceAnalysisData.averageConfidence + 0.3 * videoState.averageScore;
    } else if (hasVoice) {
      return voiceAnalysisData.averageConfidence;
    } else if (hasFacial) {
      return videoState.averageScore;
    }
    return null;
  }, [voiceAnalysisData.averageConfidence, voiceAnalysisData.messages.length, videoState.averageScore, videoState.emotionData.length]);

  useEffect(() => { setCombinedScore(calculateCombinedScore()); }, [calculateCombinedScore]);

  useEffect(() => {
    return () => {
      stopVideoAnalysis();
    };
  }, []);

  const getEmotionColor = (emotion) => {
    const colors = {
      happy: '#4CAF50', neutral: '#9E9E9E', sad: '#2196F3',
      angry: '#F44336', fear: '#673AB7', disgust: '#795548', surprise: '#FFC107'
    };
    return colors[emotion] || '#bce9ff';
  };

  // LiveKit Logic
  const [lkToken, setLkToken] = useState("");
  const [livekitUrl, setLivekitUrl] = useState("");
  const [isConnectingVoice, setIsConnectingVoice] = useState(false);

  const connectToVoiceAgent = async () => {
    if (isConnectingVoice) return;
    setIsConnectingVoice(true);
    setSessionStartTime(Date.now());
    try {
      const response = await fetch(`${API_BASE}/api/livekit/token`);
      const data = await response.json();

      if (data.error) {
        alert("Backend Error: " + data.error);
        setIsConnectingVoice(false);
        return;
      }

      setLkToken(data.token);
      setLivekitUrl(data.url);
    } catch (err) {
      console.error("Failed to connect to AI voice agent", err);
    } finally {
      setIsConnectingVoice(false);
    }
  };

  const disconnectVoiceAgent = () => {
    setLkToken("");
    // Show the report modal if we have any data
    if (voiceAnalysisData.messages.length > 0 || videoState.emotionData.length > 0) {
      setShowReportModal(true);
    }
  };

  // PDF Report Download
  const downloadReport = async () => {
    setIsGeneratingReport(true);
    try {
      const durationSeconds = sessionStartTime ? (Date.now() - sessionStartTime) / 1000 : 0;
      const score = calculateCombinedScore() || 0;

      const userMsgs = voiceAnalysisData.messages.filter(m => !m.isAgent);
      const avgVoiceConf = userMsgs.length > 0
        ? userMsgs.reduce((sum, m) => sum + (m.confidence || 0), 0) / userMsgs.length
        : 0;

      const payload = {
        session_id: `SC-${Date.now().toString(36).toUpperCase()}`,
        session_duration_seconds: durationSeconds,
        voice_messages: voiceAnalysisData.messages.map(m => ({
          text: m.text,
          isAgent: m.isAgent,
          confidence: m.confidence || null,
          severity: m.severity || null,
          is_depressed: m.is_depressed || false,
          needs_professional_help: m.needs_professional_help || false,
          timestamp: m.timestamp || null,
        })),
        facial_emotions: videoState.emotionData.map(e => ({
          emotion: e.emotion,
          score: e.score,
          timestamp: e.timestamp || null,
        })),
        voice_average_confidence: avgVoiceConf,
        facial_average_score: videoState.averageScore,
        combined_score: score,
      };

      const res = await fetch(`${API_BASE}/api/report/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error('Report generation failed');

      const arrayBuffer = await res.arrayBuffer();
      const blob = new Blob([arrayBuffer], { type: 'application/pdf' });
      const fileName = `Serene_Care_Report_${new Date().toISOString().split('T')[0]}.pdf`;
      
      // Use msSaveBlob for Edge/IE, fallback to anchor download
      if (window.navigator && window.navigator.msSaveOrOpenBlob) {
        window.navigator.msSaveOrOpenBlob(blob, fileName);
      } else {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        // Small delay to ensure DOM attachment
        setTimeout(() => {
          a.click();
          // Delay cleanup so download initiates properly
          setTimeout(() => {
            window.URL.revokeObjectURL(url);
            a.remove();
          }, 200);
        }, 100);
      }
    } catch (err) {
      console.error("Failed to download report:", err);
      alert("Failed to generate report. Please try again.");
    } finally {
      setIsGeneratingReport(false);
    }
  };

  // Confidence color helper
  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.7) return '#F44336';
    if (confidence >= 0.4) return '#FF9800';
    return '#4CAF50';
  };

  const getSeverityLabel = (score) => {
    if (score === null || score === undefined) return '';
    if (score < 0.2) return 'Minimal';
    if (score < 0.4) return 'Mild';
    if (score < 0.6) return 'Moderate';
    if (score < 0.8) return 'Moderately Severe';
    return 'Severe';
  };

  return (
    <div className="overflow-x-hidden min-h-[100dvh] text-[#dae2fd] font-['Inter'] flex">
      {/* Sidebar */}
      <nav className="hidden md:flex fixed inset-y-0 left-0 z-50 flex-col p-6 w-64 border-r border-white/5 bg-[#060e20]">
        <div className="mb-10 px-2 flex items-center gap-3">
          <span className="material-symbols-outlined text-[#87d0f0]" style={{ fontSize: "28px" }}>clinical_notes</span>
          <span className="text-xl font-bold tracking-tighter text-[#87d0f0]">Serene Care</span>
        </div>
        <div className="flex flex-col gap-2 flex-grow">
          <a className="flex items-center gap-4 px-4 py-3 text-[#87d0f0] bg-[#222a3d] rounded-xl font-semibold transition-all scale-98 hover:opacity-80" href="#">
            <span className="material-symbols-outlined active-tab">dashboard</span><span>Dashboard</span>
          </a>
        </div>
        <div className="mt-auto pt-6 border-t border-white/5">
          <div className="bg-[#171f33] p-4 rounded-2xl">
            <p className="text-xs text-[#bfc8cd] uppercase tracking-widest mb-2">System Status</p>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${videoState.isAnalyzing || !!lkToken ? 'bg-red-500 animate-pulse' : 'bg-[#87d0f0]'}`}></span>
              <span className="text-sm font-medium">{videoState.isAnalyzing || !!lkToken ? "Neural Engine Active" : "Standby"}</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="md:ml-64 p-6 md:p-8 flex-grow">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 max-w-7xl mx-auto">

          {/* Top Info Bar */}
          <header className="lg:col-span-12 flex justify-between items-center bg-[#0b1326]/60 backdrop-blur-3xl p-4 rounded-2xl shadow-lg border border-white/5">
            <div>
              <h1 className="text-2xl font-bold text-white">Diagnostic Dashboard</h1>
              <p className="text-sm text-[#bfc8cd]">Multimodal Emotion Tracking & Intervention</p>
            </div>
            {combinedScore !== null && (
              <div className="text-right">
                <p className="text-xs text-[#bfc8cd] uppercase tracking-wider">Depressive Traits Likelihood</p>
                <div className="flex items-center justify-end gap-3 mt-1">
                  <div className="w-32 h-2 bg-[#171f33] rounded-full overflow-hidden">
                    <div className="h-full transition-all duration-500" style={{
                      width: `${combinedScore * 100}%`,
                      backgroundColor: getConfidenceColor(combinedScore)
                    }}></div>
                  </div>
                  <span className="text-lg font-bold" style={{ color: getConfidenceColor(combinedScore) }}>
                    {(combinedScore * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-[10px] mt-0.5" style={{ color: getConfidenceColor(combinedScore) }}>
                  {getSeverityLabel(combinedScore)}
                </p>
              </div>
            )}
          </header>

          {/* Left Column (Video & Graphs) */}
          <div className="lg:col-span-7 flex flex-col gap-8">

            <section className="relative overflow-hidden rounded-2xl bg-[#060e20] aspect-video border border-white/5 shadow-xl group">
              <video ref={videoRefs.videoRef} autoPlay playsInline muted className="w-full h-full object-contain" style={{ display: videoState.isAnalyzing ? 'block' : 'none' }} />

              {!videoState.isAnalyzing ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#060e20]/90">
                  <span className="material-symbols-outlined text-[48px] text-[#2d3449] mb-4">videocam_off</span>
                  <p className="text-[#bfc8cd] mb-6 font-medium tracking-wide">Video stream offline</p>
                  <button onClick={startVideoAnalysis} className="px-6 py-3 bg-gradient-to-r from-[#87d0f0] to-[#2d7d9a] text-[#003545] font-bold rounded-full shadow-[0_0_30px_-5px_rgba(135,208,240,0.4)] hover:scale-105 active:scale-95 transition-all">
                    Initialize Camera
                  </button>
                </div>
              ) : (
                <>
                  <div className="absolute top-4 left-4 flex gap-2">
                    <div className="px-3 py-1.5 backdrop-blur-xl bg-[#222a3d]/50 rounded-full flex items-center gap-2 border border-white/10">
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                      <span className="text-[10px] font-bold tracking-tight text-white uppercase">Live Analysis</span>
                    </div>
                  </div>
                  <button onClick={stopVideoAnalysis} className="absolute top-4 right-4 w-10 h-10 rounded-full bg-red-500/20 text-red-400 hover:bg-red-500/40 border border-red-500/50 flex items-center justify-center transition-colors">
                    <span className="material-symbols-outlined">videocam_off</span>
                  </button>
                  <div className="absolute bottom-6 left-6 right-6">
                    <div className="bg-[#0b1326]/70 backdrop-blur-xl p-4 rounded-xl border border-white/10 inline-block">
                      <p className="text-[#bfc8cd] text-xs uppercase tracking-widest mb-1">Current State</p>
                      <h3 className="text-2xl font-bold tracking-tight text-white capitalize">
                        {videoState.dominantEmotion || "Analyzing..."}
                        {videoState.emotionData.length > 0 && <span className="ml-2 text-[#87d0f0] font-normal text-lg">({(videoState.emotionData[videoState.emotionData.length - 1].score * 100).toFixed(0)}%)</span>}
                      </h3>
                    </div>
                  </div>
                </>
              )}
              <canvas ref={videoRefs.canvasRef} style={{ display: 'none' }} />
            </section>

            <section className="bg-[#222a3d] rounded-2xl p-6 border border-white/5 shadow-xl flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-xl font-semibold tracking-tight text-white">Emotion Telemetry</h2>
                  <p className="text-xs text-[#bfc8cd]">Real-time affect mapping</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-3 mb-4">
                {['happy', 'sad', 'angry', 'fear', 'disgust', 'surprise', 'neutral'].map(emote => (
                  <div key={emote} className="flex items-center gap-1.5 bg-[#0b1326]/50 px-2 py-1 rounded">
                    <span className="w-2.5 h-2.5 rounded-full shadow-sm" style={{ backgroundColor: getEmotionColor(emote) }}></span>
                    <span className="text-[10px] text-[#dae2fd] uppercase tracking-wider font-semibold">{emote}</span>
                  </div>
                ))}
              </div>

              <div className="h-48 w-full flex items-end gap-[4px] relative overflow-x-auto group border-b border-white/10 pb-2">
                {videoState.emotionData.length > 0 ? (
                  videoState.emotionData.slice(-40).map((item, index) => (
                    <div key={index} className="w-[30px] min-w-[30px] rounded-t flex flex-col justify-end items-center pb-1 transition-all"
                      style={{ height: `${item.score * 100}%`, backgroundColor: getEmotionColor(item.emotion) }}
                      title={`${item.emotion}: ${(item.score * 100).toFixed(1)}%`}>
                      <span style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }} className="text-[9px] text-white font-bold opacity-80">{item.emotion}</span>
                    </div>
                  ))
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-[#3f484d] text-sm">
                    Connect camera to view live telemetry
                  </div>
                )}
              </div>
            </section>
          </div>

          {/* Right Column (LiveKit Chat) */}
          <div className="lg:col-span-5 relative">
            <div className="bg-[#131b2e] rounded-2xl border border-white/5 flex flex-col h-[800px] shadow-2xl sticky top-6">

              <div className="px-6 py-4 border-b border-white/5 bg-[#2d3449] flex items-center justify-between rounded-t-2xl">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-[#2d7d9a] flex items-center justify-center shadow-lg">
                    <span className="material-symbols-outlined text-[#fafdff]">psychiatry</span>
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm text-white">Serene Healthcare Assistant</h3>
                    <p className="text-[10px] text-[#87d0f0] uppercase tracking-widest">LiveKit Voice Agent</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Report button — only show when we have data and session is active or just ended */}
                  {voiceAnalysisData.messages.length > 0 && (
                    <button onClick={() => setShowReportModal(true)}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-bold uppercase tracking-wider bg-[#1a2338] text-[#87d0f0] border border-[#87d0f0]/20 hover:bg-[#87d0f0]/10 transition-all"
                      title="View session report">
                      <span className="material-symbols-outlined text-[16px]">summarize</span>
                    </button>
                  )}

                  <button onClick={!!lkToken ? disconnectVoiceAgent : connectToVoiceAgent}
                    disabled={isConnectingVoice}
                    className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider transition-all shadow-md
                              ${!!lkToken ? 'bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500/30' : 'bg-[#31394d] text-[#dae2fd] border border-white/10 hover:bg-[#3f484d] disabled:opacity-50 disabled:cursor-not-allowed'}`}>
                    <span className="material-symbols-outlined text-[18px]">
                      {isConnectingVoice ? 'hourglass_empty' : (!!lkToken ? 'stop_circle' : 'mic')}
                    </span>
                    {isConnectingVoice ? 'Connecting...' : (!!lkToken ? 'End Session' : 'Connect')}
                  </button>
                </div>
              </div>

              <div className="flex-grow overflow-y-auto p-6 space-y-6 relative">
                {!!lkToken ? (
                  <LiveKitRoom
                    token={lkToken}
                    serverUrl={livekitUrl}
                    connect={true}
                    audio={true}
                    video={false}
                    className="flex flex-col h-full"
                  >
                    <ActiveVoiceSession onAnalysisUpdate={setVoiceAnalysisData} />
                  </LiveKitRoom>
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center flex-col text-center p-8">
                    <span className="material-symbols-outlined text-[64px] text-[#2d3449] mb-4">record_voice_over</span>
                    <p className="text-[#87d0f0] font-medium mb-2">Ready to Listen</p>
                    <p className="text-[#3f484d] text-sm">Click connect to initiate a secure, real-time voice session with Serene.</p>
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </main>

      {/* ── Session Report Modal ──────────────────────────────────────────────── */}
      {showReportModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-[#131b2e] rounded-3xl border border-white/10 shadow-2xl max-w-lg w-full p-8 relative animate-[fadeIn_0.2s_ease-out]">
            {/* Close button */}
            <button onClick={() => setShowReportModal(false)}
              className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-[#bfc8cd] transition-colors">
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>

            <div className="text-center mb-6">
              <span className="material-symbols-outlined text-[48px] text-[#87d0f0] mb-3 block">monitoring</span>
              <h2 className="text-2xl font-bold text-white mb-1">Session Complete</h2>
              <p className="text-sm text-[#bfc8cd]">Multimodal depression screening summary</p>
            </div>

            {/* Combined Score Gauge */}
            {combinedScore !== null && (
              <div className="mb-6">
                <div className="flex justify-between items-end mb-2">
                  <span className="text-xs text-[#bfc8cd] uppercase tracking-widest">Combined Score</span>
                  <span className="text-3xl font-bold" style={{ color: getConfidenceColor(combinedScore) }}>
                    {(combinedScore * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="w-full h-3 bg-[#171f33] rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${combinedScore * 100}%`,
                      background: `linear-gradient(90deg, #4CAF50, #FFC107, #F44336)`
                    }}></div>
                </div>
                <p className="text-center mt-2 text-sm font-semibold" style={{ color: getConfidenceColor(combinedScore) }}>
                  {getSeverityLabel(combinedScore)}
                </p>
              </div>
            )}

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-[#1a2338] rounded-xl p-3 text-center">
                <p className="text-xl font-bold text-white">
                  {voiceAnalysisData.messages.filter(m => !m.isAgent).length}
                </p>
                <p className="text-[10px] text-[#bfc8cd] uppercase tracking-wider">Voice Messages</p>
              </div>
              <div className="bg-[#1a2338] rounded-xl p-3 text-center">
                <p className="text-xl font-bold text-white">{videoState.emotionData.length}</p>
                <p className="text-[10px] text-[#bfc8cd] uppercase tracking-wider">Face Frames</p>
              </div>
              <div className="bg-[#1a2338] rounded-xl p-3 text-center">
                <p className="text-xl font-bold text-white">
                  {sessionStartTime ? `${((Date.now() - sessionStartTime) / 60000).toFixed(1)}m` : '—'}
                </p>
                <p className="text-[10px] text-[#bfc8cd] uppercase tracking-wider">Duration</p>
              </div>
            </div>

            {/* Download button */}
            <button onClick={downloadReport} disabled={isGeneratingReport}
              className="w-full py-3.5 bg-gradient-to-r from-[#87d0f0] to-[#2d7d9a] text-[#003545] font-bold rounded-2xl shadow-[0_0_30px_-5px_rgba(135,208,240,0.3)] hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
              <span className="material-symbols-outlined text-[20px]">
                {isGeneratingReport ? 'hourglass_empty' : 'picture_as_pdf'}
              </span>
              {isGeneratingReport ? 'Generating Clinical Report...' : 'Download Clinical PDF Report'}
            </button>
            <p className="text-center text-[10px] text-[#3f484d] mt-3">
              Medical-grade report for your healthcare provider
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// Sub-component: ActiveVoiceSession  —  handles LiveKit room + NLP analysis
// ══════════════════════════════════════════════════════════════════════════════
function ActiveVoiceSession({ onAnalysisUpdate }) {
  const connectionState = useConnectionState();
  const room = useMaybeRoomContext();
  const [transcripts, setTranscripts] = useState([]);
  const chatEndRef = useRef(null);
  const analyzedIds = useRef(new Set()); // track which segments we've already sent for analysis

  const isConnected = connectionState === ConnectionState.Connected;

  // Confidence color helper
  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.7) return '#F44336';
    if (confidence >= 0.4) return '#FF9800';
    return '#4CAF50';
  };

  // Auto-scroll
  useEffect(() => {
    if (chatEndRef.current) {
      const container = chatEndRef.current.parentElement;
      if (container) {
        const isNearBottom = container.scrollHeight - container.clientHeight - container.scrollTop < 100;
        if (isNearBottom || transcripts.length <= 2) {
          chatEndRef.current.scrollIntoView({ behavior: 'auto' });
        }
      }
    }
  }, [transcripts]);

  // ── Analyze user message via backend NLP ────────────────────────────────
  const analyzeUserMessage = useCallback(async (segmentId, text) => {
    if (analyzedIds.current.has(segmentId)) return;
    analyzedIds.current.add(segmentId);

    try {
      const res = await fetch(`${API_BASE}/api/voice/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();

      if (data.status === 'success' || data.confidence !== undefined) {
        setTranscripts(prev => {
          const updated = prev.map(t => {
            if (t.segmentId === segmentId) {
              return {
                ...t,
                confidence: data.confidence,
                severity: data.severity,
                is_depressed: data.is_depressed,
                needs_professional_help: data.needs_professional_help,
                keywords_found: data.keywords_found,
                analysisComplete: true,
              };
            }
            return t;
          });
          return updated;
        });
      }
    } catch (err) {
      console.error('NLP analysis failed for segment:', segmentId, err);
    }
  }, []);

  // ── Propagate analysis data up to parent ──────────────────────────────
  useEffect(() => {
    const analyzed = transcripts.filter(t => !t.isAgent && t.analysisComplete);
    const avgConf = analyzed.length > 0
      ? analyzed.reduce((sum, t) => sum + (t.confidence || 0), 0) / analyzed.length
      : 0;

    onAnalysisUpdate({
      averageConfidence: avgConf,
      messages: transcripts.map(t => ({
        text: t.text,
        isAgent: t.isAgent,
        confidence: t.confidence || null,
        severity: t.severity || null,
        is_depressed: t.is_depressed || false,
        needs_professional_help: t.needs_professional_help || false,
        timestamp: t.timestamp,
      })),
    });
  }, [transcripts, onAnalysisUpdate]);

  // Listen for transcription events from the room
  useEffect(() => {
    if (!room || !isConnected) return;

    const handleTranscription = (segments, participant) => {
      if (!segments || segments.length === 0) return;

      const isAgent = participant?.identity?.startsWith('agent') ||
        participant?.identity?.includes('agent') ||
        !participant?.identity?.startsWith('User');

      segments.forEach(segment => {
        if (!segment.text || segment.text.trim() === '') return;

        if (segment.final) {
          setTranscripts(prev => {
            const existingIdx = prev.findIndex(t => t.segmentId === segment.id);
            if (existingIdx >= 0) {
              const updated = [...prev];
              updated[existingIdx] = {
                ...updated[existingIdx],
                text: segment.text,
                isFinal: true
              };
              return updated;
            }
            return [...prev, {
              segmentId: segment.id,
              text: segment.text,
              isAgent,
              isFinal: true,
              timestamp: Date.now()
            }];
          });

          // Trigger NLP analysis for user messages only
          if (!isAgent) {
            analyzeUserMessage(segment.id, segment.text);
          }
        } else {
          setTranscripts(prev => {
            const existingIdx = prev.findIndex(t => t.segmentId === segment.id);
            if (existingIdx >= 0) {
              const updated = [...prev];
              updated[existingIdx] = {
                ...updated[existingIdx],
                text: segment.text
              };
              return updated;
            }
            return [...prev, {
              segmentId: segment.id,
              text: segment.text,
              isAgent,
              isFinal: false,
              timestamp: Date.now()
            }];
          });
        }
      });
    };

    room.on(RoomEvent.TranscriptionReceived, handleTranscription);

    return () => {
      room.off(RoomEvent.TranscriptionReceived, handleTranscription);
    };
  }, [room, isConnected, analyzeUserMessage]);

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="text-center">
        <span className={`text-xs px-3 py-1 rounded-full uppercase tracking-widest ${isConnected
            ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
            : 'text-[#3f484d] bg-[#060e20]'
          }`}>
          {isConnected ? '● Session Connected' : 'Connecting...'}
        </span>
      </div>

      <div className="flex-grow overflow-y-auto px-2">
        {!isConnected ? (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-3">
              <div className="flex gap-1.5">
                <span className="w-2.5 h-2.5 bg-[#87d0f0] rounded-full animate-bounce"></span>
                <span className="w-2.5 h-2.5 bg-[#87d0f0] rounded-full animate-bounce" style={{ animationDelay: '0.15s' }}></span>
                <span className="w-2.5 h-2.5 bg-[#87d0f0] rounded-full animate-bounce" style={{ animationDelay: '0.3s' }}></span>
              </div>
              <p className="text-[#bfc8cd] text-sm">Establishing secure connection...</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Transcription chat messages */}
            {transcripts.map((msg, idx) => (
              <div key={msg.segmentId || idx} className={`flex gap-3 items-start ${msg.isAgent ? '' : 'flex-row-reverse'}`}>
                {msg.isAgent && (
                  <div className="w-8 h-8 rounded-full bg-[#2d7d9a] flex items-center justify-center flex-shrink-0 mt-1 shadow-lg">
                    <span className="material-symbols-outlined text-white text-[14px]">psychiatry</span>
                  </div>
                )}
                <div className="flex flex-col max-w-[80%]">
                  <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-md transition-opacity ${msg.isAgent
                      ? 'bg-[#2d3449] text-[#dae2fd] rounded-tl-none border border-white/5'
                      : 'bg-[#87d0f0]/20 text-[#87d0f0] rounded-tr-none'
                    } ${!msg.isFinal ? 'opacity-60 italic' : 'opacity-100'}`}>
                    <p>{msg.text}</p>
                  </div>

                  {/* ── Confidence badge for user messages ────────────── */}
                  {!msg.isAgent && msg.isFinal && (
                    <div className="flex items-center gap-2 mt-1.5 justify-end">
                      {msg.analysisComplete ? (
                        <>
                          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider"
                            style={{
                              backgroundColor: `${getConfidenceColor(msg.confidence)}15`,
                              color: getConfidenceColor(msg.confidence),
                              border: `1px solid ${getConfidenceColor(msg.confidence)}30`,
                            }}>
                            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: getConfidenceColor(msg.confidence) }}></span>
                            {(msg.confidence * 100).toFixed(0)}% conf
                          </div>
                          {msg.severity && msg.severity !== 'mild' && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider"
                              style={{
                                backgroundColor: msg.severity === 'severe' ? '#F4433615' : '#FF980015',
                                color: msg.severity === 'severe' ? '#F44336' : '#FF9800',
                                border: `1px solid ${msg.severity === 'severe' ? '#F4433630' : '#FF980030'}`,
                              }}>
                              {msg.severity}
                            </span>
                          )}
                          {msg.needs_professional_help && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 font-bold uppercase tracking-wider">
                              ⚠ Help
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="text-[10px] text-[#3f484d] italic">analyzing...</span>
                      )}
                    </div>
                  )}
                </div>
                {!msg.isAgent && (
                  <div className="w-8 h-8 rounded-full bg-[#3f484d] flex items-center justify-center flex-shrink-0 mt-1 shadow-lg">
                    <span className="material-symbols-outlined text-white text-[14px]">person</span>
                  </div>
                )}
              </div>
            ))}

            {/* Show audio bars if no transcripts yet */}
            {transcripts.length === 0 && (
              <>
                <div className="flex items-center justify-center gap-2 py-8">
                  <div className="flex items-center gap-1">
                    {[...Array(5)].map((_, i) => (
                      <div key={i} className="w-1 bg-[#87d0f0] rounded-full animate-pulse"
                        style={{
                          height: `${12 + Math.random() * 16}px`,
                          animationDelay: `${i * 0.15}s`,
                          animationDuration: '0.8s'
                        }}></div>
                    ))}
                  </div>
                  <span className="text-xs text-[#87d0f0] ml-2 uppercase tracking-widest font-medium">Live Session Active</span>
                  <div className="flex items-center gap-1">
                    {[...Array(5)].map((_, i) => (
                      <div key={i} className="w-1 bg-[#87d0f0] rounded-full animate-pulse"
                        style={{
                          height: `${12 + Math.random() * 16}px`,
                          animationDelay: `${(i + 5) * 0.15}s`,
                          animationDuration: '0.8s'
                        }}></div>
                    ))}
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-[#3f484d] text-xs">Speak naturally — Serene is listening and will respond automatically.</p>
                </div>
              </>
            )}

            <div ref={chatEndRef} />
          </div>
        )}
      </div>

      {/* This component renders all remote audio tracks (the agent's voice) */}
      <RoomAudioRenderer />
    </div>
  );
}

export default App;

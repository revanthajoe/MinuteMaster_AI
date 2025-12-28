import React, { useState, useRef, useEffect } from 'react';
import { 
  Upload, Mic, StopCircle, FileText, BrainCircuit, 
  MessageSquare, List, Check, RefreshCw, 
  Clock, Download, Languages, Search, ChevronRight, FileBarChart, Zap, AlignLeft
} from 'lucide-react';

// --- Configuration ---
const BACKEND_URL = 'http://127.0.0.1:5000';

export default function App() {
  // --- STATE MANAGEMENT ---
  const [view, setView] = useState('home'); 
  const [status, setStatus] = useState('idle'); 
  const [fileName, setFileName] = useState('');
  
  // Data State
  const [transcript, setTranscript] = useState([]);
  const [summary, setSummary] = useState('');
  const [history, setHistory] = useState([]);
  const [currentJobId, setCurrentJobId] = useState(null);
  
  // UI State
  const [summaryStyle, setSummaryStyle] = useState('professional');
  const [targetLang, setTargetLang] = useState('fr'); 
  const [translatedText, setTranslatedText] = useState('');
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Refs
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // --- HELPER: Dynamic Speaker Colors ---
  const getSpeakerColor = (speakerName) => {
    // Generate a consistent color from the speaker string
    if (!speakerName) return 'bg-gray-500';
    
    // Simple hash function
    let hash = 0;
    for (let i = 0; i < speakerName.length; i++) {
        hash = speakerName.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    const colors = [
        'bg-blue-600', 'bg-purple-600', 'bg-green-600', 
        'bg-yellow-600', 'bg-red-600', 'bg-indigo-600', 
        'bg-pink-600', 'bg-teal-600', 'bg-orange-600'
    ];
    
    // Pick color based on hash
    const index = Math.abs(hash) % colors.length;
    return colors[index];
  };

  // --- API FUNCTIONS ---

  const fetchHistory = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/history`);
      if (response.ok) {
        const data = await response.json();
        setHistory(data);
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    }
  };

  useEffect(() => {
    if (view === 'history') fetchHistory();
  }, [view]);

  const loadJobFromHistory = (job) => {
    setFileName(job.filename);
    setCurrentJobId(job.id);
    setSummary(job.summary || '');
    setTranslatedText(job.translated_text || '');
    
    if (typeof job.transcript === 'string') {
        const lines = job.transcript.split('\n');
        const parsed = lines.map((line) => {
            const parts = line.split(': ');
            if (parts.length >= 2) {
                return { speaker: parts[0], time: '--:--', text: parts.slice(1).join(': ') };
            }
            return { speaker: 'Unknown', time: '--:--', text: line };
        });
        setTranscript(parsed);
    } else {
        setTranscript(job.transcript || []);
    }

    if (job.summary) setStatus('summarized');
    else setStatus('transcribed');
    
    setView('home');
  };

  const transcribeAndDiarize = async (audioBlob) => {
    setStatus('processing');
    setError(null);
    setTranscript([]);
    setSummary('');
    setCurrentJobId(null);

    const formData = new FormData();
    formData.append('audio', audioBlob, fileName || 'live_recording.wav');

    try {
      const response = await fetch(`${BACKEND_URL}/transcribe`, { method: 'POST', body: formData });
      if (!response.ok) throw new Error(`Server error: ${response.statusText}`);
      const data = await response.json();
      
      if (data.results && data.results.length > 0) {
        setTranscript(data.results[0].transcript);
        setCurrentJobId(data.results[0].job_id); 
      }
      setStatus('transcribed');
    } catch (err) {
      console.error("Transcription error:", err);
      setError("Failed to process audio. Ensure backend is running.");
      setStatus('idle');
    }
  };

  // Triggered manually or when style changes
  const summarize = async (overrideStyle = null) => {
    const styleToUse = overrideStyle || summaryStyle;
    
    // If we already have a summary and just changed style, show loading
    if (summary) setStatus('summarizing'); 
    else setStatus('summarizing');

    setError(null);
    try {
      const transcriptText = transcript.map(t => `${t.speaker}: ${t.text}`).join('\n');
      
      const response = await fetch(`${BACKEND_URL}/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            text: transcriptText, 
            style: styleToUse,
            job_id: currentJobId 
        }),
      });

      if (!response.ok) throw new Error(`Server error: ${response.statusText}`);
      const data = await response.json();
      setSummary(data.summary);
      setStatus('summarized');
    } catch (err) {
      console.error("Summarization error:", err);
      setError("Failed to generate summary.");
      setStatus('transcribed');
    }
  };

  const handleStyleChange = (newStyle) => {
      setSummaryStyle(newStyle);
      // AUTO REGENERATE: If we already have a summary or transcript, generate immediately
      if (status === 'transcribed' || status === 'summarized') {
          summarize(newStyle);
      }
  };

  const translate = async () => {
      if (!summary && !transcript.length) return;
      
      // Temporary loading indicator
      const originalText = translatedText;
      setTranslatedText("Translating..."); 
      
      const textToTranslate = summary || transcript.map(t => t.text).join(' ');
      
      try {
          const response = await fetch(`${BACKEND_URL}/translate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                  text: textToTranslate,
                  source_language: 'en',
                  target_language: targetLang,
                  job_id: currentJobId
              })
          });
          
          if (!response.ok) throw new Error("Translation failed");
          const data = await response.json();
          setTranslatedText(data.translated_text);
      } catch (err) {
          setTranslatedText(originalText); // Revert
          setError("Translation failed. Check backend console for supported models.");
      }
  };

  const handleDownload = () => {
      const element = document.createElement("a");
      const content = `TRANSCRIPT:\n\n${transcript.map(t => `[${t.time}] ${t.speaker}: ${t.text}`).join('\n')}\n\nSUMMARY (${summaryStyle}):\n${summary}\n\nTRANSLATION (${targetLang}):\n${translatedText}`;
      const file = new Blob([content], {type: 'text/plain'});
      element.href = URL.createObjectURL(file);
      element.download = `${fileName || 'meeting'}_notes.txt`;
      document.body.appendChild(element);
      element.click();
  };

  // --- EVENT HANDLERS ---
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setFileName(file.name);
      transcribeAndDiarize(file);
    }
  };

  const handleStartRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setStatus('recording');
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      mediaRecorderRef.current.ondataavailable = (e) => audioChunksRef.current.push(e.data);
      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        setFileName('live_recording.wav');
        transcribeAndDiarize(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };
      mediaRecorderRef.current.start();
    } catch (err) {
      setError("Microphone access denied.");
    }
  };

  const handleStopRecording = () => {
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
  };

  // --- RENDER HELPERS ---
  const HistoryScreen = () => {
      const filteredHistory = history.filter(h => 
          h.filename.toLowerCase().includes(searchTerm.toLowerCase())
      );

      return (
        <div className="w-full">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-3xl font-bold text-white flex items-center">
                    <Clock className="mr-3 text-blue-400" /> Meeting History
                </h2>
                <div className="relative">
                    <input 
                        type="text" 
                        placeholder="Search filenames..." 
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="bg-gray-800 text-white pl-10 pr-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                </div>
            </div>
            <div className="bg-gray-800/50 rounded-xl overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-gray-700/50 text-gray-300">
                        <tr>
                            <th className="p-4">Filename</th>
                            <th className="p-4">Date</th>
                            <th className="p-4">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700">
                        {filteredHistory.map((job) => (
                            <tr key={job.id} className="hover:bg-gray-700/30 transition">
                                <td className="p-4 text-white font-medium">{job.filename}</td>
                                <td className="p-4 text-gray-400 text-sm">{new Date(job.created_at).toLocaleDateString()}</td>
                                <td className="p-4">
                                    <button onClick={() => loadJobFromHistory(job)} className="text-blue-400 hover:text-blue-300 flex items-center text-sm font-semibold">
                                        Load <ChevronRight className="h-4 w-4 ml-1" />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
      );
  };

  const WelcomeScreen = () => (
    <div className="text-center">
      <BrainCircuit className="mx-auto h-16 w-16 text-blue-400 mb-4" />
      <h1 className="text-4xl font-bold text-white mb-2">Automatic Meeting Notes</h1>
      <p className="text-lg text-gray-400 mb-8">Upload an audio file or record a new meeting to get started.</p>
      <div className="flex flex-col md:flex-row gap-4 justify-center">
        <label htmlFor="file-upload" className="w-full md:w-auto cursor-pointer bg-gray-700 hover:bg-gray-600 text-white font-bold py-3 px-6 rounded-lg flex items-center justify-center transition-all duration-300">
          <Upload className="mr-2 h-5 w-5" /> Upload Audio
        </label>
        <input id="file-upload" type="file" className="hidden" onChange={handleFileChange} accept="audio/*" />
        <button onClick={handleStartRecording} className="w-full md:w-auto bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-6 rounded-lg flex items-center justify-center transition-all duration-300">
          <Mic className="mr-2 h-5 w-5" /> Record Live
        </button>
      </div>
       {error && <p className="text-red-400 mt-4">{error}</p>}
    </div>
  );

  const ProcessingScreen = () => (
    <div className="text-center flex flex-col items-center">
      <h2 className="text-3xl font-bold text-white mb-4">
        {status === 'processing' ? 'Analyzing Audio...' : 'Generating Summary...'}
      </h2>
      <div className="w-16 h-16 border-4 border-dashed rounded-full animate-spin border-blue-500"></div>
    </div>
  );

  const ResultsScreen = () => (
    <div className="w-full">
        <div className="flex justify-between items-center mb-6">
            <h2 className="text-3xl font-bold text-white flex items-center">
                <FileText className="mr-3 text-blue-400" /> Results: {fileName}
            </h2>
            <div className="flex gap-2">
                <button onClick={handleDownload} className="bg-gray-700 hover:bg-gray-600 text-white p-2 rounded-lg" title="Download Notes">
                    <Download className="h-5 w-5" />
                </button>
                <button onClick={() => { setStatus('idle'); setView('home'); }} className="bg-gray-700 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded-lg flex items-center text-sm">
                    <RefreshCw className="mr-2 h-4 w-4" /> New
                </button>
            </div>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Transcript */}
            <div className="bg-gray-800/50 p-6 rounded-xl border border-gray-700">
                <h3 className="text-xl font-bold text-white mb-4">Transcript</h3>
                <div className="h-96 overflow-y-auto pr-2 space-y-4 scrollbar-thin scrollbar-thumb-gray-600">
                    {transcript.map((item, index) => (
                        <div key={index} className="flex gap-3">
                            {/* DYNAMIC AVATAR COLOR */}
                            <div className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center font-bold text-white text-xs ${getSpeakerColor(item.speaker)}`}>
                                {item.speaker?.charAt(item.speaker.length-1) || 'S'}
                            </div>
                            <div>
                                <div className="flex items-baseline gap-2">
                                    <span className="font-bold text-white text-sm">{item.speaker}</span>
                                    <span className="text-xs text-gray-500">{item.time}</span>
                                </div>
                                <p className="text-gray-300 text-sm">{item.text}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Summary Controls & Display */}
            <div className="bg-gray-800/50 p-6 rounded-xl border border-gray-700 flex flex-col">
                 <div className="flex flex-col gap-3 mb-4">
                     <h3 className="text-xl font-bold text-white">Summary Style</h3>
                     <div className="flex flex-wrap gap-2 bg-gray-900 p-2 rounded-lg">
                         {[
                             {id: 'professional', icon: MessageSquare, label: 'Pro'},
                             {id: 'simple', icon: AlignLeft, label: 'Simple'},
                             {id: 'bullets', icon: List, label: 'Bullets'},
                             {id: 'report', icon: FileBarChart, label: 'Report'},
                             {id: 'abstract', icon: Zap, label: 'Short'},
                             {id: 'actions', icon: Check, label: 'Actions'}
                         ].map(s => (
                             <button 
                                key={s.id} 
                                onClick={() => handleStyleChange(s.id)} 
                                className={`flex items-center gap-1 px-3 py-2 rounded-md text-xs font-semibold transition ${summaryStyle === s.id ? 'bg-blue-600 text-white shadow-lg' : 'text-gray-400 hover:bg-gray-700 hover:text-white'}`}
                             >
                                 <s.icon className="h-3 w-3" />
                                 {s.label}
                             </button>
                         ))}
                     </div>
                 </div>

                {status === 'transcribed' && !summary ? (
                  <div className="flex-grow flex flex-col items-center justify-center text-center py-10">
                    <p className="text-gray-400 mb-4">Ready to summarize.</p>
                    <button onClick={() => summarize()} className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-6 rounded-lg">Generate Summary</button>
                  </div>
                ) : (
                    <div className="flex-grow flex flex-col">
                        <div className="h-64 overflow-y-auto pr-2 text-gray-300 text-sm whitespace-pre-wrap leading-relaxed mb-4 border-b border-gray-700 pb-4">
                          {summary}
                        </div>
                        
                        {/* Translation */}
                        <div className="mt-auto pt-2">
                            <div className="flex items-center gap-2 mb-2">
                                <Languages className="h-4 w-4 text-blue-400" />
                                <span className="text-sm font-bold text-gray-300">Translate To:</span>
                                <select 
                                    value={targetLang} 
                                    onChange={(e) => setTargetLang(e.target.value)}
                                    className="bg-gray-900 text-white text-xs p-1 rounded border border-gray-700 focus:border-blue-500 outline-none"
                                >
                                    <option value="fr">French</option>
                                    <option value="es">Spanish</option>
                                    <option value="de">German</option>
                                    <option value="hi">Hindi</option>
                                    <option value="ta">Tamil</option>
                                </select>
                                <button onClick={translate} className="text-xs bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded">Translate</button>
                            </div>
                            {translatedText && (
                                <div className="p-3 bg-gray-900/50 rounded-lg text-sm text-gray-300 italic h-24 overflow-y-auto">
                                    {translatedText}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    </div>
  );

  return (
    <div className="bg-gray-900 min-h-screen text-white font-sans flex flex-col">
      <nav className="bg-gray-800 border-b border-gray-700 p-4">
          <div className="max-w-6xl mx-auto flex justify-between items-center">
            <div className="flex items-center gap-2 font-bold text-xl">
                <BrainCircuit className="text-blue-500" /> MinuteMaster AI
            </div>
            <div className="flex gap-4">
                <button onClick={() => setView('home')} className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${view === 'home' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-700'}`}>
                    <Mic className="h-4 w-4" /> Record
                </button>
                <button onClick={() => setView('history')} className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${view === 'history' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-700'}`}>
                    <Clock className="h-4 w-4" /> History
                </button>
            </div>
          </div>
      </nav>

      <main className="flex-grow flex items-center justify-center p-4">
        <div className="w-full max-w-6xl bg-black bg-opacity-20 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-gray-700/50 min-h-[600px]">
          {view === 'history' ? <HistoryScreen /> : (
              <>
                {status === 'idle' && <WelcomeScreen />}
                {status === 'recording' && (
                    <div className="text-center">
                        <div className="animate-pulse mb-6 text-red-500 font-bold">Recording Live...</div>
                        <button onClick={handleStopRecording} className="bg-red-600 hover:bg-red-500 text-white font-bold py-3 px-8 rounded-full shadow-lg flex items-center mx-auto">
                            <StopCircle className="mr-2" /> Stop Recording
                        </button>
                    </div>
                )}
                {(status === 'processing' || status === 'summarizing') && <ProcessingScreen />}
                {(status === 'transcribed' || status === 'summarized') && <ResultsScreen />}
              </>
          )}
        </div>
      </main>
    </div>
  );
}
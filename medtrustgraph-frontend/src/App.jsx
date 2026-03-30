import React, { useState, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { AlertTriangle, Search, Activity, X, CheckCircle } from 'lucide-react';

export default function App() {
  const [queryText, setQueryText] = useState('');
  
  const [patientData, setPatientData] = useState({
    age: '', gender: '', diseases: '', hereditary: '', habits: '', dynamicFields: {}
  });

  // ✨ ADD THESE TWO LINES FOR MANUAL FIELDS
  const [newFieldKey, setNewFieldKey] = useState('');
  const [newFieldValue, setNewFieldValue] = useState('');

  const [loading, setLoading] = useState(false);
  const [queryData, setQueryData] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState(null);

  const [activeTab, setActiveTab] = useState('clinical'); 
  const [radarItems, setRadarItems] = useState([]); 
  const [radarInput, setRadarInput] = useState(''); 

  // NEW: State for the FDA Diet Plan
  const [dietPlan, setDietPlan] = useState(null);
  const [dietLoading, setDietLoading] = useState(false);

  const pollingInterval = useRef(null);
  const resultsRef = useRef(null);

  const [isReadingPdf, setIsReadingPdf] = useState(false);


  const scrollToResults = () => {
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 150);
  };

  // ✨ ADD THIS FUNCTION
  const handleAddCustomField = () => {
    if (!newFieldKey.trim()) return;
    
    setPatientData(prev => ({
      ...prev,
      dynamicFields: {
        ...(prev.dynamicFields || {}),
        [newFieldKey.trim()]: newFieldValue
      }
    }));
    
    // Clear the inputs after adding
    setNewFieldKey('');
    setNewFieldValue('');
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsReadingPdf(true);
    const formData = new FormData();
    formData.append("file", file); // "file" must match the parameter name in Python

    try {
        const response = await fetch("http://localhost:8000/parse-report", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (data.error) {
            alert("Error reading PDF: " + data.error);
        } else {
            // SUCCESS! Update your specific patientData state object
            setPatientData(prev => ({
              ...prev,
              age: data.age || prev.age,
              gender: data.gender || prev.gender,
              diseases: data.diseases || prev.diseases,
              habits: data.habits || prev.habits,
              hereditary: data.hereditary || prev.hereditary,
              dynamicFields: data.dynamic_fields || prev.dynamicFields // <--- ADD THIS LINE
            }));
            
            console.log("AI Extracted Data:", data);
        }
    } catch (error) {
        console.error("Upload failed:", error);
        alert("Failed to connect to the AI parser.");
    } finally {
        setIsReadingPdf(false);
        event.target.value = null; // Reset the input 
    }
  };

  const handleAddRadarItem = (e) => {
    if (e.key === 'Enter' && radarInput.trim() !== '') {
      e.preventDefault();
      if (radarItems.length >= 10) {
        alert("Maximum of 10 items allowed to prevent API rate limits.");
        return;
      }
      if (!radarItems.includes(radarInput.trim())) {
        setRadarItems([...radarItems, radarInput.trim()]);
      }
      setRadarInput('');
    }
  };

  const handleRemoveRadarItem = (itemToRemove) => {
    setRadarItems(radarItems.filter(item => item !== itemToRemove));
  };
  
  const formatTextToReact = (text) => {
    if (!text) return null;
    
    return text.split('\n').map((line, lineIndex) => {
      if (line.trim() === '') return <div key={lineIndex} className="h-3"></div>;
      
      let cleanLine = line.trim();
      let isBullet = false;
      let isH2 = false;
      let isH3 = false;

      if (cleanLine.startsWith('### ')) {
        isH3 = true; cleanLine = cleanLine.substring(4);
      } else if (cleanLine.startsWith('## ')) {
        isH2 = true; cleanLine = cleanLine.substring(3);
      } else if (cleanLine.startsWith('# ')) {
        isH2 = true; cleanLine = cleanLine.substring(2); 
      }

      if (cleanLine.startsWith('* ') || cleanLine.startsWith('- ')) {
        isBullet = true; cleanLine = cleanLine.substring(2);
      }

      cleanLine = cleanLine.replace(/(?:^\*|^\s\*)([^\*].*?)\*\*/g, '**$1**');
      
      const parts = cleanLine.split(/(\*\*.*?\*\*|\[(?:PMID:\s*)?[\d,\s]+\])/g);
      
      const formattedParts = parts.map((part, partIndex) => {
        if (!part) return null;
        
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={partIndex} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
        }
        
        if (part.match(/^\[(?:PMID:\s*)?[\d,\s]+\]$/)) {
          const rawNumbers = part.replace(/\[|\]|PMID:/g, '');
          const pmids = rawNumbers.split(',');
          
          return (
            <span key={partIndex} className="mx-1">
              [{pmids.map((id, k) => {
                const cleanId = id.trim();
                return (
                  <React.Fragment key={k}>
                    <a href={`https://pubmed.ncbi.nlm.nih.gov/${cleanId}/`} target="_blank" rel="noreferrer" 
                       className="text-blue-600 font-bold hover:underline bg-blue-100 px-1 rounded mx-0.5 shadow-sm">
                      {cleanId}
                    </a>
                    {k < pmids.length - 1 ? ', ' : ''}
                  </React.Fragment>
                );
              })}]
            </span>
          );
        }
        return <span key={partIndex}>{part}</span>;
      });
      
      if (isH2) return <h2 key={lineIndex} className="text-xl font-bold text-slate-800 mt-5 mb-2 border-b pb-1 border-slate-200">{formattedParts}</h2>;
      if (isH3) return <h3 key={lineIndex} className="text-lg font-bold text-slate-700 mt-4 mb-1">{formattedParts}</h3>;
      if (isBullet) return <li key={lineIndex} className="ml-6 list-disc mb-2 pl-1 leading-relaxed text-slate-700">{formattedParts}</li>;
      
      return <p key={lineIndex} className="mb-2 leading-relaxed text-slate-700">{formattedParts}</p>;
    });
  };

  // NEW: Fetch Diet Plan directly from Python backend
  const fetchDietPlan = async (drugs) => {
    setDietLoading(true);

    // ✨ Package the dynamic fields for the Diet plan
    const extraInfo = Object.entries(patientData.dynamicFields || {})
        .map(([key, value]) => `${key}: ${value}`)
        .join(', ');

    try {
      // Pointing directly to your Python FastAPI port 8000
      const res = await fetch('http://localhost:8000/generate-diet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            drugs: drugs,
            age: patientData.age, 
            gender: patientData.gender,
            diseases: patientData.diseases, 
            hereditary: patientData.hereditary, 
            habits: patientData.habits,
            additional_context: extraInfo // ✨ Sent directly to Python FastAPI!
        })
      });
      const data = await res.json();
      setDietPlan(data);
    } catch (err) {
      console.error("Failed to fetch diet plan:", err);
    } finally {
      setDietLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!queryText.trim()) return;
    setLoading(true); setQueryData(null); setGraphData({ nodes: [], links: [] });

    scrollToResults();

    // ✨ Package the dynamic fields
    const extraInfo = Object.entries(patientData.dynamicFields || {})
        .map(([key, value]) => `${key}: ${value}`)
        .join(', ');

    try {
      const res = await fetch('http://localhost:8080/api/queries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            questionText: queryText,
            age: patientData.age, 
            gender: patientData.gender,
            diseases: patientData.diseases, // <--- No more hack! Pure diseases data.
            hereditary: patientData.hereditary, 
            habits: patientData.habits,
            additionalContext: extraInfo // ✨ Sent cleanly to Java!
        })
      });
      const data = await res.json();
      pollStatus(data.id);
    } catch (err) {
      console.error(err); setLoading(false);
    }
  };

  const handleRadarSearch = async () => {
    if (radarItems.length < 2) return; 
    setLoading(true); setQueryData(null); setGraphData({ nodes: [], links: [] });
    setDietPlan(null); 

    scrollToResults();

    fetchDietPlan(radarItems);

    const drugList = radarItems.join(", ");
    const secretQueryText = `RADAR_QUERY: ${drugList}`;

    // ✨ Package the dynamic fields here too!
    const extraInfo = Object.entries(patientData.dynamicFields || {})
        .map(([key, value]) => `${key}: ${value}`)
        .join(', ');

    try {
      const res = await fetch('http://localhost:8080/api/queries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            questionText: secretQueryText,
            age: patientData.age, 
            gender: patientData.gender,
            diseases: patientData.diseases, 
            hereditary: patientData.hereditary, 
            habits: patientData.habits,
            additionalContext: extraInfo // ✨ SEND TO JAVA HERE
        })
      });

      if (res.ok) {
        const newQuery = await res.json();
        pollStatus(newQuery.id); 
      } else {
        setLoading(false);
      }
    } catch (error) {
      console.error(error); setLoading(false);
    }
  };

  const pollStatus = (id) => {
    if (pollingInterval.current) clearInterval(pollingInterval.current);
    pollingInterval.current = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8080/api/queries/${id}`);
        const data = await res.json();
        
        if (data.finalAnswer && !data.finalAnswer.includes('Processing...')) {
          clearInterval(pollingInterval.current);
          setQueryData(data);
          setLoading(false);
          fetchGraphData(id);
        } else {
          setQueryData(data);
        }
      } catch (err) {
        console.error(err);
      }
    }, 3000);
  };

  const fetchGraphData = async (id) => {
    try {
      const res = await fetch(`http://localhost:8080/api/queries/${id}/graph`);
      const data = await res.json();
      
      const nodes = data.nodes.map(c => ({
        id: c.aiNodeId, 
        name: c.claimText,
        color: c.isPruned ? '#ef4444' : '#22c55e', 
        trust: c.finalTrust,
        // ✨ ADD THIS LINE to pull the PubMed IDs
        sources: c.sourceIndices || c.sources || "" 
      }));

      const links = data.edges.map(e => ({
        source: e.sourceNode, target: e.targetNode, weight: e.weight
      }));

      setGraphData({ nodes, links });
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
      <header className="bg-slate-900 text-white p-8 text-center shadow-lg min-h-screen flex flex-col justify-center items-center w-full relative">
        <h1 className="text-4xl font-extrabold tracking-tight">MedTrustGraph</h1>
        <p className="text-blue-300 mt-2 text-lg">Neuro-Symbolic AI for Medical Evidence Resolution</p>
        
        <div className="flex justify-center mb-8">
          <div className="bg-slate-800/60 p-1 rounded-lg border border-slate-700 inline-flex mt-6">
            <button onClick={() => setActiveTab('clinical')} className={`px-6 py-2 rounded-md text-sm font-bold transition-all ${activeTab === 'clinical' ? 'bg-blue-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'}`}>Clinical QA Search</button>
            <button onClick={() => setActiveTab('radar')} className={`px-6 py-2 rounded-md text-sm font-bold transition-all ${activeTab === 'radar' ? 'bg-purple-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'}`}>Interaction Radar (Polypharmacy)</button>
          </div>
        </div>

        {activeTab === 'clinical' ? (
          <div className="flex flex-col md:flex-row gap-4 max-w-4xl mx-auto w-full">
            <div className="flex-grow bg-slate-800/50 p-2 rounded-xl border border-slate-700 flex items-center shadow-inner relative transition-all focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500">
              <Search className="text-slate-400 ml-3 mr-2" size={24} />
              <input type="text" value={queryText} onChange={(e) => setQueryText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSearch()} placeholder="Ask a medical question (e.g., Is Metformin safe for...)" className="w-full bg-transparent text-slate-100 placeholder-slate-500 p-3 focus:outline-none text-lg" />
            </div>
            <button onClick={handleSearch} disabled={loading || !queryText.trim()} className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white px-8 py-4 rounded-xl font-bold transition-all shadow-lg flex items-center justify-center gap-2 min-w-[160px]">
              {loading ? <span className="animate-pulse">Analyzing...</span> : "Analyze Evidence"}
            </button>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto w-full bg-slate-800/50 p-6 rounded-xl border border-purple-500/50 shadow-lg">
            <h2 className="text-purple-300 font-bold mb-2 flex items-center gap-2"><Activity size={20} /> Polypharmacy & Dietary Radar</h2>
            <p className="text-slate-400 text-sm mb-4">Type a drug, supplement, or food and press Enter to add it to the interaction matrix.</p>
            
            <div className="flex flex-wrap gap-2 mb-4 min-h-[40px] p-2 bg-slate-900/50 rounded-lg border border-slate-700">
              {radarItems.length === 0 && <span className="text-slate-500 text-sm italic py-1 px-2">No items added yet...</span>}
              {radarItems.map((item, index) => (
                <span key={index} className="bg-purple-600 text-white px-3 py-1 rounded-full text-sm font-semibold flex items-center gap-2 shadow-sm">
                  {item} <button onClick={() => handleRemoveRadarItem(item)} className="hover:text-purple-200 bg-purple-700 rounded-full p-0.5"><X size={14} /></button>
                </span>
              ))}
            </div>

            <div className="flex gap-4">
              <input type="text" value={radarInput} onChange={(e) => setRadarInput(e.target.value)} onKeyDown={handleAddRadarItem} placeholder="e.g., Warfarin, Grapefruit, Ibuprofen..." className="flex-grow bg-slate-900 border border-slate-600 text-slate-100 p-3 rounded-lg focus:outline-none focus:border-purple-500" />
              <button onClick={handleRadarSearch} disabled={radarItems.length < 2 || loading} className="bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white px-8 py-3 rounded-lg font-bold transition-all shadow-md">
                {loading ? <span className="animate-pulse">Scanning...</span> : "Scan Interactions"}
              </button>
            </div>
          </div>
        )}

        <div className="mt-6 max-w-4xl mx-auto bg-slate-800/40 p-5 rounded-xl border border-slate-700 shadow-xl backdrop-blur-sm">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-blue-300 font-semibold text-sm uppercase tracking-wider flex items-center gap-2">Patient Clinical Profile (Optional)</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="flex flex-col"><label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Age</label><input type="number" placeholder="e.g., 65" className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200" value={patientData.age} onChange={e => setPatientData({...patientData, age: e.target.value})} /></div>
            <div className="flex flex-col"><label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Gender</label><select className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200" value={patientData.gender} onChange={e => setPatientData({...patientData, gender: e.target.value})}><option value="">Select Gender...</option><option value="Male">Male</option><option value="Female">Female</option></select></div>
            <div className="flex flex-col lg:col-span-2"><label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Lifestyle / Habits</label><input type="text" placeholder="e.g., Heavy smoker" className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200" value={patientData.habits} onChange={e => setPatientData({...patientData, habits: e.target.value})} /></div>
            <div className="flex flex-col lg:col-span-2"><label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Chronic Diseases</label><input type="text" placeholder="e.g., Hypertension" className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200" value={patientData.diseases} onChange={e => setPatientData({...patientData, diseases: e.target.value})} /></div>
            <div className="flex flex-col lg:col-span-2"><label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Hereditary History</label><input type="text" placeholder="e.g., Family history of early MI" className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200" value={patientData.hereditary} onChange={e => setPatientData({...patientData, hereditary: e.target.value})} /></div>
            {/* DYNAMIC FIELDS RENDERED BY AI OR MANUAL */}
            {patientData.dynamicFields && Object.entries(patientData.dynamicFields).map(([key, value]) => (
              <div key={key} className="flex flex-col lg:col-span-2 relative group">
                <label className="text-purple-400 text-xs mb-1 ml-1 font-bold flex items-center gap-1">✨ {key}</label>
                <input 
                  type="text" 
                  className="p-2.5 bg-slate-900/60 border border-purple-500/50 rounded-lg text-sm text-slate-200 shadow-[0_0_10px_rgba(168,85,247,0.2)]" 
                  value={value} 
                  onChange={e => setPatientData({
                    ...patientData, 
                    dynamicFields: { ...patientData.dynamicFields, [key]: e.target.value }
                  })} 
                />
              </div>
            ))}

            {/* ✨ ADD CUSTOM FIELD UI */}
            <div className="flex flex-col lg:col-span-4 mt-2 p-3 bg-slate-800/40 rounded-xl border border-slate-600 border-dashed transition-all hover:border-slate-400">
              <label className="text-slate-400 text-xs mb-2 ml-1 font-bold flex items-center gap-2">➕ Add Custom Medical Field</label>
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  placeholder="Field Name (e.g., Blood Type)"
                  className="p-2.5 flex-1 bg-slate-900/80 border border-slate-600 rounded-lg text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
                  value={newFieldKey}
                  onChange={e => setNewFieldKey(e.target.value)}
                />
                <input
                  type="text"
                  placeholder="Value (e.g., O+)"
                  className="p-2.5 flex-1 bg-slate-900/80 border border-slate-600 rounded-lg text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
                  value={newFieldValue}
                  onChange={e => setNewFieldValue(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddCustomField()}
                />
                <button
                  onClick={handleAddCustomField}
                  disabled={!newFieldKey.trim()}
                  className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white px-6 py-2.5 rounded-lg font-bold transition-all text-sm"
                >
                  Add Field
                </button>
              </div>
            </div>
          </div>
        </div>
        <div className="pdf-upload-container" style={{ marginBottom: '20px' }}>
            <input
                type="file"
                id="report-upload"
                accept="application/pdf"
                style={{ display: 'none' }}
                onChange={handleFileUpload}
            />
            <label 
                htmlFor="report-upload" 
                style={{ 
                    cursor: isReadingPdf ? 'not-allowed' : 'pointer', 
                    padding: '10px 15px', 
                    backgroundColor: isReadingPdf ? '#ccc' : '#4F46E5', 
                    color: 'white', 
                    borderRadius: '6px',
                    fontWeight: 'bold',
                    display: 'inline-block'
                }}
            >
                {isReadingPdf ? "🤖 AI is reading report..." : "📄 Auto-Fill from PDF Report"}
            </label>
        </div>
      </header>

      <main ref={resultsRef} className="flex-grow p-8 flex flex-col gap-8 max-w-[1600px] mx-auto w-full items-start min-h-screen pt-16">
        
        <div className="w-full flex flex-col lg:flex-row gap-6">
          <div className="w-full lg:w-1/2 bg-white p-6 rounded-xl shadow-md border-t-4 border-slate-400">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Baseline RAG</h2>
            <p className="text-sm text-slate-500 mb-4">Standard LLM approach without graph pruning.</p>
            
            <div className="text-slate-800 bg-slate-50 p-5 rounded-lg min-h-[120px] max-h-[500px] overflow-y-auto text-lg border border-slate-200">
              {loading && !queryData?.baselineAnswer ? (
                <span className="animate-pulse flex items-center gap-2"><Activity size={18}/> Synthesizing baseline...</span>
              ) : (
                <div className="font-medium">
                  {formatTextToReact(queryData?.baselineAnswer || "Waiting for query...")}
                </div>
              )}
            </div>
          </div>

          <div className="w-full lg:w-1/2 bg-white p-6 rounded-xl shadow-md border-t-4 border-blue-600 relative">
            <h2 className="text-2xl font-bold text-blue-900 mb-2">MedTrustGraph Conclusion</h2>
            <p className="text-sm text-slate-500 mb-4">Mathematically verified via NLI Trust Propagation.</p>
            
            {queryData?.hasConflict && (
              <div className="absolute top-6 right-6 bg-red-100 text-red-700 px-4 py-1.5 rounded-full text-sm font-bold border border-red-300 flex items-center gap-2 shadow-sm">
                <AlertTriangle size={16} /> High Conflict Detected
              </div>
            )}

            <div className="text-slate-800 bg-blue-50/50 p-5 rounded-lg min-h-[120px] max-h-[500px] overflow-y-auto text-lg border border-blue-100">
              {loading ? (
                <span className="animate-pulse flex items-center gap-2 text-blue-600"><Activity size={18}/> Building trust graph...</span>
              ) : (
                <div className="font-medium">
                  {formatTextToReact(queryData?.finalAnswer || "Waiting for query...")}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* =========================================
            NEW: PERSONALIZED DIETARY PLAN UI 
            ========================================= */}
        {activeTab === 'radar' && (dietPlan || dietLoading) && (
          <div className="w-full bg-white p-6 rounded-xl shadow-md border-t-4 border-emerald-500">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Personalized Dietary & Lifestyle Plan</h2>
            <p className="text-sm text-slate-500 mb-6">Synthesized dynamically from openFDA labels and clinical guidelines.</p>

            {dietLoading ? (
              <div className="flex items-center justify-center py-8 text-emerald-600 animate-pulse font-medium text-lg">
                <Activity size={24} className="mr-3" /> Fetching authoritative FDA data and analyzing restrictions...
              </div>
            ) : (
              <div className="flex flex-col md:flex-row gap-6">
                {/* Avoid Column */}
                <div className="flex-1 bg-red-50/50 p-5 rounded-xl border border-red-200 shadow-sm">
                  <h3 className="text-lg font-bold text-red-800 mb-4 flex items-center gap-2 border-b border-red-200 pb-2">
                    <AlertTriangle size={20} className="text-red-600" /> Foods & Habits to Strictly Avoid
                  </h3>
                  <ul className="space-y-4">
                    {dietPlan?.avoid?.map((item, idx) => (
                      <li key={idx} className="flex flex-col bg-white p-3 rounded-lg border border-red-100 shadow-sm">
                        <span className="font-bold text-red-900 text-lg">{item.food}</span>
                        <span className="text-sm text-slate-700 mt-1">{item.reason}</span>
                      </li>
                    ))}
                    {(!dietPlan?.avoid || dietPlan.avoid.length === 0) && (
                      <span className="text-sm text-slate-500 italic">No strict FDA dietary warnings found for these medications.</span>
                    )}
                  </ul>
                </div>

                {/* Recommend Column */}
                <div className="flex-1 bg-emerald-50/50 p-5 rounded-xl border border-emerald-200 shadow-sm">
                  <h3 className="text-lg font-bold text-emerald-800 mb-4 flex items-center gap-2 border-b border-emerald-200 pb-2">
                    <CheckCircle size={20} className="text-emerald-600" /> Recommended Clinical Diet
                  </h3>
                  <ul className="space-y-4">
                    {dietPlan?.recommend?.map((item, idx) => (
                      <li key={idx} className="flex flex-col bg-white p-3 rounded-lg border border-emerald-100 shadow-sm">
                        <span className="font-bold text-emerald-900 text-lg">{item.food}</span>
                        <span className="text-sm text-slate-700 mt-1">{item.reason}</span>
                      </li>
                    ))}
                    {(!dietPlan?.recommend || dietPlan.recommend.length === 0) && (
                      <span className="text-sm text-slate-500 italic">Add patient diseases to see tailored nutritional recommendations.</span>
                    )}
                  </ul>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="w-full bg-white rounded-xl shadow-md border border-slate-200 flex flex-col overflow-hidden h-[700px]">
          <div className="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
            <h2 className="text-lg font-bold text-slate-800">Evidence Graph Topology</h2>
            <div className="text-xs font-medium text-slate-600 flex gap-4">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></span> Trusted</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-500 shadow-sm"></span> Pruned</span>
              <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-green-500"></span> Agreement</span>
              <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-red-500"></span> Contradiction</span>
            </div>
          </div>
          <div className="flex-grow bg-slate-900 relative overflow-hidden">
             {graphData.nodes.length > 0 ? (
                <ForceGraph2D
                  graphData={graphData}
                  onNodeClick={(node) => setSelectedNode(node)}
                  linkColor={link => link.weight === -1 ? '#ef4444' : '#22c55e'}
                  linkWidth={2}
                  linkDirectionalParticles={2}
                  linkDirectionalParticleSpeed={0.01}
                  onNodeDragEnd={node => { node.fx = node.x; node.fy = node.y; }}
                  d3Force={(d3, d3Force) => {
                    d3Force('charge').strength(-500);
                    d3Force('link').distance(100);
                  }}
                  nodeCanvasObject={(node, ctx, globalScale) => {
                    const words = node.name ? node.name.split(' ') : [''];
                    const shortText = words.slice(0, 5).join(' ') + (words.length > 5 ? '...' : '');
                    
                    const label = activeTab === 'radar' 
                      ? 'Interaction Claim' 
                      : `Trust: ${node.trust ? node.trust.toFixed(2) : '0.00'}`;

                    if (activeTab === 'radar') {
                      ctx.beginPath();
                      ctx.arc(node.x - 8, node.y, 6, Math.PI/2, -Math.PI/2); 
                      ctx.lineTo(node.x + 8, node.y - 6);                    
                      ctx.arc(node.x + 8, node.y, 6, -Math.PI/2, Math.PI/2); 
                      ctx.closePath();
                      
                      ctx.fillStyle = '#ffffff'; 
                      ctx.fill();
                      
                      ctx.strokeStyle = '#94a3b8';
                      ctx.lineWidth = 1;
                      ctx.stroke();
                      
                      ctx.beginPath();
                      ctx.moveTo(node.x, node.y - 5);
                      ctx.lineTo(node.x, node.y + 5);
                      ctx.strokeStyle = '#94a3b8'; 
                      ctx.lineWidth = 1.5;
                      ctx.stroke();
                      
                    } else {
                      ctx.beginPath();
                      ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI, false);
                      ctx.fillStyle = node.color;
                      ctx.fill();
                    }

                    const fontSize = 12 / globalScale;
                    ctx.font = `bold ${fontSize}px Sans-Serif`;
                    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                    
                    ctx.fillStyle = '#ffffff';
                    ctx.fillText(label, node.x, node.y - 14);
                    
                    ctx.font = `${fontSize * 0.9}px Sans-Serif`;
                    ctx.fillStyle = '#94a3b8';
                    ctx.fillText(shortText, node.x, node.y + 14);
                  }}
                  backgroundColor="#0f172a"
                />
             ) : (
                <div className="absolute inset-0 flex items-center justify-center text-slate-400 font-medium">
                  {loading ? 'Generating 2D WebGL Graph...' : 'Enter a query to visualize evidence nodes.'}
                </div>
             )}

              {/* ✨ INTERACTIVE SIDEBAR UI ✨ */}
              {selectedNode && (
                <div className="absolute top-0 right-0 w-80 md:w-96 h-full bg-slate-800/95 backdrop-blur-md border-l border-slate-600 shadow-2xl p-5 flex flex-col z-10 transition-all duration-300">
                  <div className="flex justify-between items-start mb-4 border-b border-slate-600 pb-3">
                    <h3 className="text-lg font-bold text-white flex items-center gap-2">
                      <Activity size={18} className="text-blue-400"/> Node Details
                    </h3>
                    <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-white bg-slate-700 hover:bg-slate-600 rounded-full p-1 transition-colors">
                      <X size={18} />
                    </button>
                  </div>
                  
                  <div className="flex-grow overflow-y-auto pr-2">
                    <div className="mb-4">
                      <span className={`px-3 py-1 text-xs font-bold rounded-full ${selectedNode.color === '#22c55e' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                        {selectedNode.color === '#22c55e' ? '✓ Trusted Evidence' : '✗ Pruned (Conflict)'}
                      </span>
                    </div>
                    
                    <div className="mb-5">
                      <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1 block">Extracted Claim</label>
                      <p className="text-slate-200 text-sm leading-relaxed bg-slate-900/50 p-3 rounded-lg border border-slate-700/50">
                        {selectedNode.name}
                      </p>
                    </div>

                    <div className="mb-5">
                      <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1 block">NLI Trust Score</label>
                      <div className="flex items-center gap-3 bg-slate-900/50 p-3 rounded-lg border border-slate-700/50">
                        <div className="w-full bg-slate-700 rounded-full h-2.5">
                          <div className={`h-2.5 rounded-full ${selectedNode.color === '#22c55e' ? 'bg-green-500' : 'bg-red-500'}`} style={{ width: `${Math.max(0, Math.min(100, selectedNode.trust * 100))}%` }}></div>
                        </div>
                        <span className="text-white font-mono text-sm">{selectedNode.trust ? selectedNode.trust.toFixed(2) : '0.00'}</span>
                      </div>
                    </div>

                    <div>
                      <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2 block">PubMed Sources</label>
                      {selectedNode.sources ? (
                        <div className="flex flex-wrap gap-2">
                          {selectedNode.sources.split(',').map((pmid, idx) => {
                            const cleanPmid = pmid.trim();
                            if (!cleanPmid) return null;
                            return (
                              <a key={idx} href={`https://pubmed.ncbi.nlm.nih.gov/${cleanPmid}/`} target="_blank" rel="noreferrer" className="flex items-center gap-1 bg-blue-600/20 text-blue-400 border border-blue-500/30 hover:bg-blue-600 hover:text-white px-3 py-2 rounded-lg text-sm font-bold transition-all shadow-sm">
                                <Search size={14} /> PMID: {cleanPmid}
                              </a>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-slate-500 text-sm italic p-3 bg-slate-900/50 rounded-lg">No specific PMIDs linked to this node.</p>
                      )}
                    </div>
                  </div>
                </div>
              )}
          </div>
        </div>
      </main>
    </div>
  );
}
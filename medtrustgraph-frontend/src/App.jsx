import React, { useState, useEffect, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { AlertTriangle, Search, Activity, X } from 'lucide-react';

export default function App() {
  const [queryText, setQueryText] = useState('');
  
  // NEW: Store the form data
  const [patientData, setPatientData] = useState({
    age: '',
    gender: '',
    diseases: '',
    hereditary: '',
    habits: ''
  });

  const [loading, setLoading] = useState(false);
  const [queryData, setQueryData] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });

  const [activeTab, setActiveTab] = useState('clinical'); // 'clinical' or 'radar'
  const [radarItems, setRadarItems] = useState([]); // Stores the list of drugs/foods
  const [radarInput, setRadarInput] = useState(''); // Stores what is currently being typed


  // Adds a drug/food to the radar list when they press Enter
  const handleAddRadarItem = (e) => {
    if (e.key === 'Enter' && radarInput.trim() !== '') {
      e.preventDefault();
      
      // NEW: Prevent API explosion!
      if (radarItems.length >= 5) {
        alert("Maximum of 5 items allowed to prevent API rate limits.");
        return;
      }

      if (!radarItems.includes(radarInput.trim())) {
        setRadarItems([...radarItems, radarInput.trim()]);
      }
      setRadarInput('');
    }
  };

  // Removes an item if they click the X
  const handleRemoveRadarItem = (itemToRemove) => {
    setRadarItems(radarItems.filter(item => item !== itemToRemove));
  };
  
  const pollingInterval = useRef(null);

  const formatCitations = (text) => {
    if (!text) return text;
    const parts = text.split(/(\[PMID:\s*[\d,\s]+\])/g);
    return parts.map((part, index) => {
      if (part.startsWith('[PMID:')) {
        const pmids = part.replace('[PMID:', '').replace(']', '').split(',');
        return (
          <span key={index} className="mx-1">
            [{pmids.map((id) => (
              <a key={id} href={`https://pubmed.ncbi.nlm.nih.gov/${id.trim()}/`} target="_blank" rel="noreferrer" 
                 className="text-blue-600 font-bold hover:underline bg-blue-100 px-1 rounded mx-0.5">
                {id.trim()}
              </a>
            ))}]
          </span>
        );
      }
      return part;
    });
  };

  const handleSearch = async () => {
    if (!queryText.trim()) return;
    setLoading(true);
    setQueryData(null);
    setGraphData({ nodes: [], links: [] });

    try {
      const res = await fetch('http://localhost:8080/api/queries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            questionText: queryText,
            age: patientData.age,
            gender: patientData.gender,
            diseases: patientData.diseases,
            hereditary: patientData.hereditary,
            habits: patientData.habits
        })
      });
      const data = await res.json();
      pollStatus(data.id);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };
  // ==========================================
  // NEW: Handle Radar Search
  // ==========================================
  const handleRadarSearch = async () => {
    if (radarItems.length < 2) return; // Need at least 2 items to compare!
    
    setLoading(true);
    setQueryData(null);
    setGraphData({ nodes: [], links: [] });

    // Combine the tags into our secret routing string
    const drugList = radarItems.join(", ");
    const secretQueryText = `RADAR_QUERY: ${drugList}`;

    try {
      // We use the EXACT same Spring Boot endpoint, so we don't have to change Java at all!
      const res = await fetch('http://localhost:8080/api/queries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            questionText: secretQueryText,
            age: patientData.age,
            gender: patientData.gender,
            diseases: patientData.diseases,
            hereditary: patientData.hereditary,
            habits: patientData.habits
        })
      });

      if (res.ok) {
        const newQuery = await res.json();
        setSelectedQueryId(newQuery.id); // This triggers your existing polling effect!
      } else {
        console.error("Failed to start radar process");
        setLoading(false);
      }
    } catch (error) {
      console.error("Error connecting to backend:", error);
      setLoading(false);
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
        id: c.aiNodeId, // Use the AI ID so edges connect properly
        name: c.claimText,
        color: c.isPruned ? '#ef4444' : '#22c55e', // Red if pruned, Green if kept
        trust: c.finalTrust
      }));

      const links = data.edges.map(e => ({
        source: e.sourceNode,
        target: e.targetNode,
        weight: e.weight
      }));

      setGraphData({ nodes, links });
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
      <header className="bg-slate-900 text-white p-8 text-center shadow-lg">
        <h1 className="text-4xl font-extrabold tracking-tight">MedTrustGraph</h1>
        <p className="text-blue-300 mt-2 text-lg">Neuro-Symbolic AI for Medical Evidence Resolution</p>
        
        {/* ========================================== */}
        {/* TAB NAVIGATION */}
        {/* ========================================== */}
        <div className="flex justify-center mb-8">
          <div className="bg-slate-800/60 p-1 rounded-lg border border-slate-700 inline-flex">
            <button 
              onClick={() => setActiveTab('clinical')}
              className={`px-6 py-2 rounded-md text-sm font-bold transition-all ${activeTab === 'clinical' ? 'bg-blue-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Clinical QA Search
            </button>
            <button 
              onClick={() => setActiveTab('radar')}
              className={`px-6 py-2 rounded-md text-sm font-bold transition-all ${activeTab === 'radar' ? 'bg-purple-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Interaction Radar (Polypharmacy)
            </button>
          </div>
        </div>

        {/* ========================================== */}
        {/* CONDITIONAL RENDER: WHICH TAB IS ACTIVE? */}
        {/* ========================================== */}
        
        {activeTab === 'clinical' ? (
          // --- TAB 1: YOUR ORIGINAL CLINICAL SEARCH ---
          <div className="flex flex-col md:flex-row gap-4 max-w-4xl mx-auto">
            <div className="flex-grow bg-slate-800/50 p-2 rounded-xl border border-slate-700 flex items-center shadow-inner relative transition-all focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500">
              <Search className="text-slate-400 ml-3 mr-2" size={24} />
              <input 
                type="text" 
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Ask a medical question (e.g., Is Metformin safe for...)" 
                className="w-full bg-transparent text-slate-100 placeholder-slate-500 p-3 focus:outline-none text-lg"
              />
            </div>
            <button 
              onClick={handleSearch}
              disabled={loading || !queryText.trim()}
              className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white px-8 py-4 rounded-xl font-bold transition-all shadow-lg flex items-center justify-center gap-2 min-w-[160px]"
            >
              {loading ? <span className="animate-pulse">Analyzing...</span> : "Analyze Evidence"}
            </button>
          </div>
        ) : (
          // --- TAB 2: THE NEW INTERACTION RADAR ---
          <div className="max-w-4xl mx-auto bg-slate-800/50 p-6 rounded-xl border border-purple-500/50 shadow-lg">
            <h2 className="text-purple-300 font-bold mb-2 flex items-center gap-2">
              <Activity size={20} /> Polypharmacy & Dietary Radar
            </h2>
            <p className="text-slate-400 text-sm mb-4">Type a drug, supplement, or food and press Enter to add it to the interaction matrix.</p>
            
            {/* The Tag Display Area */}
            <div className="flex flex-wrap gap-2 mb-4 min-h-[40px] p-2 bg-slate-900/50 rounded-lg border border-slate-700">
              {radarItems.length === 0 && <span className="text-slate-500 text-sm italic py-1 px-2">No items added yet...</span>}
              {radarItems.map((item, index) => (
                <span key={index} className="bg-purple-600 text-white px-3 py-1 rounded-full text-sm font-semibold flex items-center gap-2 shadow-sm">
                  {item}
                  <button onClick={() => handleRemoveRadarItem(item)} className="hover:text-purple-200 bg-purple-700 rounded-full p-0.5">
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>

            {/* The Input Field */}
            <div className="flex gap-4">
              <input 
                type="text" 
                value={radarInput}
                onChange={(e) => setRadarInput(e.target.value)}
                onKeyDown={handleAddRadarItem}
                placeholder="e.g., Warfarin, Grapefruit, Ibuprofen..." 
                className="flex-grow bg-slate-900 border border-slate-600 text-slate-100 p-3 rounded-lg focus:outline-none focus:border-purple-500"
              />
              <button 
                onClick={handleRadarSearch}
                disabled={radarItems.length < 2 || loading}
                className="bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white px-8 py-3 rounded-lg font-bold transition-all shadow-md"
              >
                {loading ? <span className="animate-pulse">Scanning...</span> : "Scan Interactions"}
              </button>
            </div>
          </div>
        )}

        {/* ========================================== */}
        {/* PATIENT INTAKE FORM (MODULAR CDSS FEATURE) */}
        {/* ========================================== */}
        <div className="mt-6 max-w-4xl mx-auto bg-slate-800/40 p-5 rounded-xl border border-slate-700 shadow-xl backdrop-blur-sm">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-blue-300 font-semibold text-sm uppercase tracking-wider flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
              Patient Clinical Profile (Optional)
            </h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Age */}
            <div className="flex flex-col">
              <label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Age</label>
              <input type="number" placeholder="e.g., 65" 
                className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 focus:outline-none transition-all"
                value={patientData.age} onChange={e => setPatientData({...patientData, age: e.target.value})} />
            </div>

            {/* Gender */}
            <div className="flex flex-col">
              <label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Gender</label>
              <select className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 focus:outline-none transition-all"
                value={patientData.gender} onChange={e => setPatientData({...patientData, gender: e.target.value})}>
                <option value="">Select Gender...</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>

            {/* Habits */}
            <div className="flex flex-col lg:col-span-2">
              <label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Lifestyle / Habits</label>
              <input type="text" placeholder="e.g., Heavy smoker, occasional alcohol" 
                className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 focus:outline-none transition-all"
                value={patientData.habits} onChange={e => setPatientData({...patientData, habits: e.target.value})} />
            </div>

            {/* Chronic Diseases */}
            <div className="flex flex-col lg:col-span-2">
              <label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Chronic Diseases / Conditions</label>
              <input type="text" placeholder="e.g., Stage 4 CKD, Hypertension, Peptic Ulcers" 
                className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 focus:outline-none transition-all"
                value={patientData.diseases} onChange={e => setPatientData({...patientData, diseases: e.target.value})} />
            </div>

            {/* Hereditary */}
            <div className="flex flex-col lg:col-span-2">
              <label className="text-slate-400 text-xs mb-1 ml-1 font-medium">Hereditary History</label>
              <input type="text" placeholder="e.g., Family history of early myocardial infarction" 
                className="p-2.5 bg-slate-900/60 border border-slate-600 rounded-lg text-sm text-slate-200 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 focus:outline-none transition-all"
                value={patientData.hereditary} onChange={e => setPatientData({...patientData, hereditary: e.target.value})} />
            </div>
          </div>
        </div>
      </header>

      {/* FIX 2: Added items-start to main, which allows sticky elements to work properly */}
      <main className="flex-grow p-8 flex flex-col lg:flex-row gap-8 max-w-[1600px] mx-auto w-full items-start">
        
        {/* Left Column */}
        <div className="w-full lg:w-1/2 flex flex-col gap-6">
          <div className="bg-white p-6 rounded-xl shadow-md border-t-4 border-slate-400">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Baseline RAG</h2>
            <p className="text-sm text-slate-500 mb-4">Standard LLM approach without graph pruning.</p>
            
            {/* NEW: Added whitespace-pre-wrap here! */}
            <div className="whitespace-pre-wrap text-slate-700 bg-slate-50 p-5 rounded-lg min-h-[120px] text-lg leading-relaxed border border-slate-200">
              {loading && !queryData?.baselineAnswer ? (
                <span className="animate-pulse flex items-center gap-2"><Activity size={18}/> Synthesizing baseline...</span>
              ) : formatCitations(queryData?.baselineAnswer || "Waiting for query...")}
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl shadow-md border-t-4 border-blue-600 relative">
            <h2 className="text-2xl font-bold text-blue-900 mb-2">MedTrustGraph Conclusion</h2>
            <p className="text-sm text-slate-500 mb-4">Mathematically verified via NLI Trust Propagation.</p>
            
            {queryData?.hasConflict && (
              <div className="absolute top-6 right-6 bg-red-100 text-red-700 px-4 py-1.5 rounded-full text-sm font-bold border border-red-300 flex items-center gap-2 shadow-sm">
                <AlertTriangle size={16} /> High Conflict Detected
              </div>
            )}

            {/* NEW: Added whitespace-pre-wrap to this div below! */}
            <div className="whitespace-pre-wrap text-slate-800 bg-blue-50/50 p-5 rounded-lg min-h-[120px] text-lg leading-relaxed border border-blue-100">
              {loading ? (
                <span className="animate-pulse flex items-center gap-2 text-blue-600">
                  <Activity size={18}/> Building trust graph & extracting claims (~20s)...
                </span>
              ) : formatCitations(queryData?.finalAnswer || "Waiting for query...")}
            </div>
          </div>
        </div>

        {/* Right Column: FIX 2: Added sticky top-8 so the graph follows you as you scroll! */}
        <div className="w-full lg:w-1/2 bg-white rounded-xl shadow-md border border-slate-200 flex flex-col overflow-hidden h-[600px] sticky top-8">
          <div className="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
            <h2 className="text-lg font-bold text-slate-800">Evidence Graph Topology</h2>
            <div className="text-xs font-medium text-slate-600 flex gap-4">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></span> Trusted</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-500 shadow-sm"></span> Pruned</span>
              <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-green-500"></span> Agreement</span>
              <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-red-500"></span> Contradiction</span>
            </div>
          </div>
          <div className="flex-grow bg-slate-900 relative">
             {graphData.nodes.length > 0 ? (
                <ForceGraph2D
                  graphData={graphData}
                  linkColor={link => link.weight === -1 ? '#ef4444' : '#22c55e'}
                  linkWidth={2}
                  linkDirectionalParticles={2}
                  linkDirectionalParticleSpeed={0.01}
                  
                  // ==========================================
                  // NEW FIX 1: Pin the node when dropped
                  // ==========================================
                  onNodeDragEnd={node => {
                    node.fx = node.x;
                    node.fy = node.y;
                  }}

                  // ==========================================
                  // NEW FIX 2: Space the nodes out 
                  // ==========================================
                  d3Force={(d3, d3Force) => {
                    d3Force('charge').strength(-400); // Higher negative number pushes them further apart
                    d3Force('link').distance(80);     // Makes the connecting lines longer
                  }}

                  nodeCanvasObject={(node, ctx, globalScale) => {
                    // Create a short text label (first 5 words)
                    const words = node.name ? node.name.split(' ') : [''];
                    const shortText = words.slice(0, 5).join(' ') + (words.length > 5 ? '...' : '');
                    const label = `Trust: ${node.trust ? node.trust.toFixed(2) : '0.00'}`;

                    // Draw the Node Circle
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI, false);
                    ctx.fillStyle = node.color;
                    ctx.fill();

                    // Draw the text labels
                    const fontSize = 12 / globalScale;
                    ctx.font = `bold ${fontSize}px Sans-Serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    
                    // Trust Score
                    ctx.fillStyle = '#ffffff';
                    ctx.fillText(label, node.x, node.y - 12);
                    
                    // Claim snippet
                    ctx.font = `${fontSize * 0.9}px Sans-Serif`;
                    ctx.fillStyle = '#94a3b8';
                    ctx.fillText(shortText, node.x, node.y + 12);
                  }}
                  backgroundColor="#0f172a"
                />
             ) : (
                <div className="absolute inset-0 flex items-center justify-center text-slate-400 font-medium">
                  {loading ? 'Generating 2D WebGL Graph...' : 'Enter a query to visualize evidence nodes.'}
                </div>
             )}
          </div>
        </div>
      </main>
    </div>
  );
}
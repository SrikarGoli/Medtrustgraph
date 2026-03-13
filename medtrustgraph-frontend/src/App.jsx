import React, { useState, useEffect, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { AlertTriangle, Search, Activity } from 'lucide-react';

export default function App() {
  const [queryText, setQueryText] = useState('');
  const [patientContext, setPatientContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [queryData, setQueryData] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  
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
            patientContext: patientContext // SEND IT TO BACKEND
        })
      });
      const data = await res.json();
      pollStatus(data.id);
    } catch (err) {
      console.error(err);
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
        
        <div className="mt-8 max-w-3xl mx-auto flex shadow-xl">
          {/* FIX 1: Added bg-white and text-gray-900 so it is clearly visible! */}
          <input 
            type="text" 
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-grow p-4 rounded-l-lg bg-white text-gray-900 focus:outline-none text-lg placeholder-gray-500" 
            placeholder="e.g., Does aspirin increase or decrease the risk of heart attacks?"
          />
          <button 
            onClick={handleSearch}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-400 px-8 py-4 rounded-r-lg font-bold transition-colors flex items-center gap-2"
          >
            {loading ? <Activity className="animate-spin" /> : <Search />}
            Analyze
          </button>
        </div>
        <div className="mt-8 max-w-3xl mx-auto flex shadow-xl">
          {/* ... your existing main search input and button ... */}
        </div>

        {/* NEW PATIENT CONTEXT INPUT */}
        <div className="mt-4 max-w-3xl mx-auto flex">
          <div className="flex-grow bg-slate-800/50 p-1 rounded-lg border border-slate-700 flex items-center">
            <span className="text-slate-400 font-semibold px-4 text-sm whitespace-nowrap">
              Patient Context (Optional):
            </span>
            <input 
              type="text" 
              value={patientContext}
              onChange={(e) => setPatientContext(e.target.value)}
              className="flex-grow p-2 bg-transparent text-blue-200 focus:outline-none text-sm placeholder-slate-500" 
              placeholder="e.g., 65-year-old male with chronic kidney disease"
            />
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
            <div className="text-slate-700 bg-slate-50 p-5 rounded-lg min-h-[120px] text-lg leading-relaxed border border-slate-200">
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

            <div className="text-slate-800 bg-blue-50/50 p-5 rounded-lg min-h-[120px] text-lg leading-relaxed border border-blue-100">
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
                  // FIX 3 & 4: Draw edges, animate them, and draw custom text on nodes!
                  linkColor={link => link.weight === -1 ? '#ef4444' : '#22c55e'}
                  linkWidth={2}
                  linkDirectionalParticles={2}
                  linkDirectionalParticleSpeed={0.01}
                  nodeCanvasObject={(node, ctx, globalScale) => {
                    // Create a short text label (first 5 words)
                    const words = node.name.split(' ');
                    const shortText = words.slice(0, 5).join(' ') + (words.length > 5 ? '...' : '');
                    const label = `Trust: ${node.trust.toFixed(2)}`;

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
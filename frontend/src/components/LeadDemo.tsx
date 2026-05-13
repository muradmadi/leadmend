/**
 * @packageDocumentation
 * Interactive lead processing visualizer for the LeadMend frontend.
 * 
 * @remarks
 * This module provides the core demo experience, simulating a multi-stage
 * lead enrichment and routing pipeline. It is designed to demonstrate
 * "self-healing" capabilities (e.g., email extraction from messages) and
 * firmographic-based routing logic in a user-friendly, visual way.
 * 
 * The architecture separates pure logic (logic generation) from stateful
 * UI (pipeline orchestration) to ensure maintainability.
 */

import React, { useState, useEffect, useMemo } from 'react';

/**
 * Configuration for a specific demo scenario.
 */
interface Scenario {
  /** Unique identifier for the scenario button. */
  id: string;
  /** Human-readable name displayed in the selector. */
  name: string;
  /** Short summary of what this scenario tests. */
  description: string;
  /** The raw JSON data sent to the backend webhook. */
  payload: any;
  /**
   * If true, appends a query parameter to force a mock failure in the enrichment stage.
   * @defaultValue `false`
   */
  simulateFailure?: boolean;
  /** 
   * The classification of the scenario used to determine the specific
   * explanation logic and visual indicators in the UI.
   */
  type: 'perfect' | 'missing_email' | 'garbage' | 'duplicate' | 'enrichment_down';
}

const SCENARIOS: Scenario[] = [
  {
    id: 'perfect',
    name: 'Perfect Enterprise Lead',
    type: 'perfect',
    description: 'A clean, high-value lead with all fields populated.',
    payload: {
      name: 'Sarah Chen',
      email: 'sarah.chen@techflow.ai',
      company: 'TechFlow AI',
      website: 'https://techflow.ai',
      message: 'Looking for an enterprise-grade lead routing solution.',
      source: 'demo'
    }
  },
  {
    id: 'missing-email',
    name: 'Missing Email (Recovered)',
    type: 'missing_email',
    description: 'Email field is empty, but exists in the message body.',
    payload: {
      name: 'Marcus Thorne',
      email: '',
      company: 'Thorne Global',
      website: 'https://thorne.global',
      message: 'Contact me at marcus.t@thorne.global regarding the platform.',
      source: 'demo'
    }
  },
  {
    id: 'garbage',
    name: 'Garbage Data',
    type: 'garbage',
    description: 'Empty or nonsensical input.',
    payload: {
      name: '???',
      email: 'asdf@jkl',
      company: '',
      website: '',
      message: '1234567890',
      source: 'demo'
    }
  },
  {
    id: 'duplicate',
    name: 'Duplicate Lead',
    type: 'duplicate',
    description: 'An email that already exists in the database.',
    payload: {
      name: 'Sarah Chen',
      email: 'sarah.chen@techflow.ai',
      company: 'TechFlow AI',
      website: 'https://techflow.ai',
      message: 'Sending another message to check status.',
      source: 'demo'
    }
  },
  {
    id: 'enrich-down',
    name: 'Enrichment API Down',
    type: 'enrichment_down',
    description: 'Simulates a failure in the external enrichment service.',
    simulateFailure: true,
    payload: {
      name: 'Alex Rivera',
      email: 'alex@startup.io',
      company: 'Startup IO',
      website: 'https://startup.io',
      message: 'Interested in the API documentation.',
      source: 'demo'
    }
  }
];

/**
 * Generates a human-readable explanation of the pipeline's decision-making process.
 * 
 * @remarks
 * This is a pure function that translates raw API response metadata into natural 
 * language. It follows a strict priority-based logic:
 * 1. **Deduplication:** Duplicates are always flagged first.
 * 2. **Validation:** Garbage data that fails initial checks.
 * 3. **Infrastructure:** External service failures (Enrichment Down).
 * 4. **Self-Healing:** Successful recoveries (Missing Email).
 * 5. **Scoring:** Tier-based outcomes for valid leads.
 * 
 * @param response - The structured data returned from the `/api/v1/lead` endpoint.
 * @param scenario - The current active scenario configuration.
 * @returns A string containing the descriptive explanation of the result.
 */
function generatePipelineLogic(
  response: {
    score: number;
    is_duplicate: boolean;
    routing: string;
    enriched_data: {
      industry: string;
      company_size: string;
      company_name: string;
    };
    email: string;
    original_payload_had_email: boolean;
    validation_warnings?: string[];
  },
  scenario: {
    type: 'perfect' | 'missing_email' | 'garbage' | 'duplicate' | 'enrichment_down';
  }
): string {
  const {
    score,
    is_duplicate,
    routing,
    enriched_data,
    email,
    original_payload_had_email,
    validation_warnings
  } = response;
  const { industry, company_size } = enriched_data;

  // Rules applied in order:
  
  // 1. Duplicate result
  if (is_duplicate) {
    return `The deduplicator found an existing lead with the same email (${email}). To prevent double‑outreach, the score was set to 0 and the lead was routed to ${routing} for manual review.`;
  }

  // 2. Garbage scenario
  if (score === 0 && routing === '#ops-invalid') {
    return `The pipeline detected invalid input data (missing email, no company, empty message). Enrichment was skipped entirely, score set to 0, and the lead was routed to ${routing} for disposal.`;
  }

  // 3. Enrichment down scenario
  if (industry === 'Unknown' && company_size === 'Unknown') {
    return `The enrichment API was unreachable. The pipeline fell back to default values and internal heuristics. Score reduced to ${score}, routed to ${routing} for manual review.`;
  }

  // 4. Missing email scenario
  if (original_payload_had_email === false) {
    return `The incoming payload was missing an email field. The self‑healing logic extracted ${email} from the message body. Enrichment then proceeded normally. Final score ${score}, routed to ${routing}.`;
  }

  // 5. High-value lead
  if (score >= 50) {
    return `All fields validated, enrichment returned complete firmographic data (industry: ${industry}, size: ${company_size}). No duplicates found. High‑value lead, routed to ${routing} for immediate follow‑up.`;
  }

  // 6. Mid-market lead
  if (score >= 20) {
    return `The lead passed validation and enrichment, but scored in the mid‑market range (industry: ${industry}, size: ${company_size}). Routed to ${routing} for nurturing.`;
  }

  // 7. Low-priority lead
  const baseExplanation = `The pipeline processed the lead but the data was minimal or the enrichment returned weak signals. Score ${score}, routed to ${routing}.`;

  if (validation_warnings && validation_warnings.length > 0) {
    return `${baseExplanation}\n\nNote: ${validation_warnings.join(", ")}`;
  }

  return baseExplanation;
}

/**
 * Definition of the linear pipeline stages.
 * These are used to drive the visual progress bar during processing.
 */
const STAGES = [
  { id: 'validate', name: 'Validate' },
  { id: 'enrich', name: 'Enrich' },
  { id: 'dedupe', name: 'Deduplicate' },
  { id: 'score', name: 'Score' },
  { id: 'route', name: 'Route' }
];

const baseUrl = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * The primary interactive component for the LeadMend demo.
 *
 * @remarks
 * This component manages the state of a simulated lead processing run. 
 * It employs a "Perceived Performance" strategy: while the backend call is fast,
 * the UI explicitly delays transitions between stages (Validate -> Enrich -> etc.)
 * to allow the user to digest the multi-step nature of the pipeline.
 *
 * It utilizes `useMemo` for JSON syntax highlighting to prevent expensive
 * string manipulation on every re-render while the progress bar is animating.
 *
 * @returns A structured layout containing a scenario selector, payload preview,
 * and a pipeline visualizer that resolves into a results panel.
 *
 * @example
 * ```tsx
 * // Used as a React island in Astro
 * <LeadDemo client:load />
 * ```
 */
const LeadDemo = () => {
  const [selectedScenario, setSelectedScenario] = useState<Scenario>(SCENARIOS[0]);
  const [currentStage, setCurrentStage] = useState<number>(-1); // -1: idle, 0-4: stages, 5: complete
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [dynamicExplanation, setDynamicExplanation] = useState<string>('');
  const [resetMessage, setResetMessage] = useState<string>('');

  // buildExplanation was removed in favor of generatePipelineLogic

  const handleResetDatabase = async () => {
    try {
      const res = await fetch(`${baseUrl}/api/v1/reset`, { method: 'POST' });
      if (res.ok) {
        setResult(null);
        setCurrentStage(-1);
        setResetMessage('Database cleared — ready for a fresh demo.');
        setTimeout(() => setResetMessage(''), 3000);
      }
    } catch (err) {
      console.error('Reset error:', err);
    }
  };

  const handleRunPipeline = async () => {
    setIsProcessing(true);
    setCurrentStage(0);
    setResult(null);

    const payload = { ...selectedScenario.payload };
    
    // We introduce artificial delays here to ensure the user can observe each 
    // stage of the pipeline. In a production environment, this visual 
    // orchestration would be replaced by real-time WebSocket or Long-Polling updates.
    for (let i = 0; i < STAGES.length; i++) {
      setCurrentStage(i);
      await new Promise(resolve => setTimeout(resolve, 600));
    }

    try {
      const endpoint = selectedScenario.simulateFailure 
        ? `${baseUrl}/api/v1/lead?simulate_failure=true` 
        : `${baseUrl}/api/v1/lead`;

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      setResult(data);
      
      const logicExplanation = generatePipelineLogic({
        score: data.score,
        is_duplicate: data.is_duplicate,
        routing: data.routing_channel,
        enriched_data: data.enriched_data,
        email: data.email,
        original_payload_had_email: data.original_payload_had_email,
        validation_warnings: data.validation_warnings
      }, selectedScenario);
      
      setDynamicExplanation(logicExplanation);
      setCurrentStage(5);
    } catch (err) {
      console.error('Pipeline error:', err);
      const fallbackData = {
        score: 0,
        is_duplicate: false,
        routing_channel: '#error-log',
        enriched_data: { industry: 'Unknown', company_size: 'Unknown', company_name: 'Unknown' },
        email: selectedScenario.payload.email || 'unknown@unknown.com',
        original_payload_had_email: !!selectedScenario.payload.email
      };
      setResult(fallbackData);
      setDynamicExplanation(generatePipelineLogic({
        ...fallbackData,
        routing: fallbackData.routing_channel
      }, selectedScenario));
      setCurrentStage(5);
    } finally {
      setIsProcessing(false);
    }
  };

  const highlightedJson = useMemo(() => {
    const json = JSON.stringify(selectedScenario.payload, null, 2);
    return json.split('\n').map((line, i) => {
      // We use a basic regex-based split to identify JSON keys for styling.
      // This is a lightweight alternative to full-blown syntax highlighting 
      // libraries, keeping the bundle size small while providing a premium feel.
      const parts = line.split(/(".*?"):\s/);
      if (parts.length > 1) {
        return (
          <div key={i} className="whitespace-pre">
            <span className="text-lm-accent">{parts[1]}</span>
            <span className="text-lm-border">: </span>
            <span className="text-lm-text">{parts[2]}</span>
          </div>
        );
      }
      return <div key={i} className="text-lm-border">{line}</div>;
    });
  }, [selectedScenario]);

  return (
    <div className="space-y-8 animate-in fade-in duration-700">
      <section>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
          <label className="block text-[10px] font-medium font-body text-lm-text opacity-40 uppercase tracking-[0.5px]">
            Select Scenario
          </label>
          <div className="flex items-center gap-4">
            {resetMessage && (
              <span className="text-[10px] font-medium text-lm-accent animate-pulse">
                {resetMessage}
              </span>
            )}
            <button
              onClick={handleResetDatabase}
              className="text-[10px] font-medium text-lm-text opacity-60 hover:opacity-100 transition-opacity uppercase tracking-[1px] border border-lm-border px-3 py-1 hover:border-lm-accent"
            >
              Reset Database
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {SCENARIOS.map((s) => (
            <button
              key={s.id}
              onClick={() => {
                if (!isProcessing) {
                  setSelectedScenario(s);
                  setCurrentStage(-1);
                  setResult(null);
                  setDynamicExplanation('');
                }
              }}
              className={`p-4 text-left border border-lm-border transition-all duration-200 ${
                selectedScenario.id === s.id
                  ? 'bg-[#3a3a3c] border-l-2 border-l-lm-accent'
                  : 'bg-lm-card hover:bg-[#343436]'
              } ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <h3 className="font-body font-medium text-sm text-lm-text">{s.name}</h3>
              <p className="text-[11px] text-lm-text opacity-50 mt-1 line-clamp-1">{s.description}</p>
            </button>
          ))}
        </div>
      </section>

      <div className="bg-lm-card p-8 border border-lm-border shadow-2xl">
        <div className="space-y-8">
          {/* 3. Payload Preview */}
          <section>
            <label className="block text-[10px] font-medium font-body text-lm-text opacity-40 uppercase tracking-[0.5px] mb-4">
              Incoming Payload (Webhook JSON)
            </label>
            <div className="bg-lm-bg p-4 font-mono text-[13px] leading-relaxed border border-lm-border overflow-x-auto min-h-[160px]">
              {highlightedJson}
            </div>
          </section>

          {/* 4. The Form (Read-only) */}
          <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-[10px] font-medium text-lm-text opacity-40 uppercase tracking-[0.5px]">Name</label>
              <input
                readOnly
                value={selectedScenario.payload.name}
                className="w-full bg-lm-bg border border-lm-border p-3 text-sm font-body text-lm-text outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-medium text-lm-text opacity-40 uppercase tracking-[0.5px]">Email</label>
              <input
                readOnly
                value={selectedScenario.payload.email}
                className="w-full bg-lm-bg border border-lm-border p-3 text-sm font-body text-lm-text outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-medium text-lm-text opacity-40 uppercase tracking-[0.5px]">Company</label>
              <input
                readOnly
                value={selectedScenario.payload.company}
                className="w-full bg-lm-bg border border-lm-border p-3 text-sm font-body text-lm-text outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-medium text-lm-text opacity-40 uppercase tracking-[0.5px]">Website</label>
              <input
                readOnly
                value={selectedScenario.payload.website}
                className="w-full bg-lm-bg border border-lm-border p-3 text-sm font-body text-lm-text outline-none"
              />
            </div>
            <div className="md:col-span-2 space-y-2">
              <label className="text-[10px] font-medium text-lm-text opacity-40 uppercase tracking-[0.5px]">Message</label>
              <textarea
                readOnly
                value={selectedScenario.payload.message}
                rows={3}
                className="w-full bg-lm-bg border border-lm-border p-3 text-sm font-body text-lm-text outline-none resize-none"
              />
            </div>
          </section>

          {/* Button */}
          <button
            onClick={handleRunPipeline}
            disabled={isProcessing}
            className={`w-full py-4 font-body font-medium text-sm tracking-[2px] uppercase border border-lm-accent transition-all duration-250
              ${isProcessing 
                ? 'opacity-50 cursor-not-allowed' 
                : 'text-lm-accent hover:bg-lm-accent hover:text-lm-bg focus:bg-lm-accent focus:text-lm-bg focus:outline focus:outline-2 focus:outline-white'
              }`}
          >
            {isProcessing ? 'Processing Pipeline...' : 'Run Pipeline'}
          </button>
        </div>
      </div>

      {/* 5. Pipeline Visualizer */}
      {(isProcessing || currentStage >= 0) && (
        <section className="animate-in slide-in-from-top-4 duration-500">
          <div className="flex justify-between items-center relative py-8 px-4">
            {/* Connector Line */}
            <div className="absolute top-1/2 left-0 w-full h-[1px] bg-lm-border -z-10 transform -translate-y-1/2"></div>
            
            {STAGES.map((stage, idx) => {
              const isActive = currentStage === idx;
              const isCompleted = currentStage > idx;
              const isEnrichmentSkipped = stage.id === 'enrich' && selectedScenario.type === 'garbage' && currentStage >= idx;

              return (
                <div key={stage.id} className="flex flex-col items-center space-y-3 bg-lm-bg">
                  <div 
                    className={`w-8 h-8 flex items-center justify-center border transition-all duration-300 ${
                      isEnrichmentSkipped ? 'border-lm-border bg-lm-card text-lm-text opacity-30 grayscale' :
                      isActive ? 'border-lm-accent bg-lm-accent text-lm-bg scale-110' :
                      isCompleted ? 'border-lm-accent bg-lm-accent text-lm-bg' :
                      'border-lm-border bg-lm-bg text-lm-text opacity-40'
                    }`}
                  >
                    {isCompleted && !isEnrichmentSkipped ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <span className="text-[10px] font-mono">{idx + 1}</span>
                    )}
                  </div>
                  <span className={`text-[10px] font-medium uppercase tracking-wider ${
                    isEnrichmentSkipped ? 'text-lm-text opacity-20' :
                    isActive ? 'text-lm-accent' : 'text-lm-text opacity-40'
                  }`}>
                    {isEnrichmentSkipped ? 'Skipped' : stage.name}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* 6. Results Panel */}
      {currentStage === 5 && result && (
        <div className="animate-in fade-in slide-in-from-bottom-8 duration-700 space-y-6">
          <div className="bg-lm-card border border-lm-border p-8 shadow-2xl">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-6">
                <div>
                  <label className="block text-[10px] font-medium font-body text-lm-text opacity-40 uppercase tracking-[0.5px] mb-2">Lead Score</label>
                  <span className={`font-heading text-6xl font-bold ${result.score > 70 ? 'text-lm-accent' : 'text-lm-text opacity-60'}`}>
                    {result.score}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-medium font-body text-lm-text opacity-40 uppercase tracking-[0.5px] mb-1">Duplicate?</label>
                    <span className="font-mono text-sm uppercase">{result.is_duplicate ? 'YES' : 'NO'}</span>
                  </div>
                  <div>
                    <label className="block text-[10px] font-medium font-body text-lm-text opacity-40 uppercase tracking-[0.5px] mb-1">Routing</label>
                    <span className="font-mono text-sm text-lm-accent">{result.routing_channel}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-4 border-l border-lm-border pl-8">
                <label className="block text-[10px] font-medium font-body text-lm-text opacity-40 uppercase tracking-[0.5px] mb-2">Enriched Data</label>
                <div className="space-y-3">
                  <div className="flex justify-between items-center py-2 border-b border-lm-border">
                    <span className="text-xs text-lm-text opacity-40">Industry</span>
                    <span className="font-mono text-xs">{result.enriched_data?.industry || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-lm-border">
                    <span className="text-xs text-lm-text opacity-40">Company Size</span>
                    <span className="font-mono text-xs">{result.enriched_data?.company_size || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-lm-border">
                    <span className="text-xs text-lm-text opacity-40">Company Name</span>
                    <span className="font-mono text-xs">{result.enriched_data?.company_name || result.company || 'N/A'}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 7. Explanation Block */}
          <div className="bg-[#3a3a3c] p-6 border-l-2 border-lm-accent whitespace-pre-wrap">
            <label className="block text-[10px] font-medium font-body text-lm-accent uppercase tracking-[0.5px] mb-2">Pipeline Logic</label>
            <p className="text-sm font-body leading-relaxed text-lm-text opacity-80">
              {dynamicExplanation}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default LeadDemo;

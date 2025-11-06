'use client';

import { AskResponse } from '@/lib/api';
import { AlertCircle, CheckCircle, XCircle, Clock, BookOpen, AlertTriangle, ExternalLink, Sparkles, ThumbsUp, ThumbsDown, Plus, Check } from 'lucide-react';
import { useState, useEffect } from 'react';
import { api } from '@/lib/api';

interface AnswerCardProps {
  result: AskResponse;
}

export default function AnswerCard({ result }: AnswerCardProps) {
  const { answer, citations, completeness_check, enrichment_data, latency_ms, question, retrieved_docs, documents_used } = result;

  const [userRating, setUserRating] = useState<'up' | 'down' | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState('');
  
  // State for URL ingestion
  const [urlStates, setUrlStates] = useState<Record<string, {
    isAdding: boolean;
    added: boolean;
    error: string | null;
    alreadyExists: boolean;
  }>>({});

  // Check if URLs already exist in KB
  useEffect(() => {
    if (enrichment_data?.sources_found) {
      enrichment_data.sources_found.forEach(async (source) => {
        try {
          const response = await api.checkUrl(source.url);
          if (response.exists) {
            setUrlStates(prev => ({
              ...prev,
              [source.url]: {
                isAdding: false,
                added: false,
                error: null,
                alreadyExists: true
              }
            }));
          }
        } catch (error) {
          // Ignore errors in existence check
        }
      });
    }
  }, [enrichment_data]);

  const handleAddToKB = async (url: string, title: string) => {
    setUrlStates(prev => ({
      ...prev,
      [url]: { isAdding: true, added: false, error: null, alreadyExists: false }
    }));

    try {
      const response = await api.ingestUrl({ url, title });
      
      setUrlStates(prev => ({
        ...prev,
        [url]: {
          isAdding: false,
          added: true,
          error: null,
          alreadyExists: response.already_exists
        }
      }));
    } catch (error) {
      setUrlStates(prev => ({
        ...prev,
        [url]: {
          isAdding: false,
          added: false,
          error: error instanceof Error ? error.message : 'Failed to add to KB',
          alreadyExists: false
        }
      }));
    }
  };

  const handleRating = async (rating: 'up' | 'down') => {
    if (userRating) return; // Already rated
    
    setUserRating(rating);
    setShowFeedback(true);
  };

  const submitRating = async () => {
    if (!userRating) return;

    setIsSubmitting(true);
    setSubmitMessage('');

    try {
      const response = await api.submitRating({
        question,
        answer,
        rating: userRating,
        feedback_text: feedbackText || undefined,
        documents_used,
        retrieved_docs,
        completeness: completeness_check.is_complete ? 'complete' : 'incomplete'
      });

      setSubmitMessage(response.message);
      setShowFeedback(false);
    } catch (error) {
      setSubmitMessage('Failed to submit rating. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Helper function to clean filename by removing hash prefix
  const cleanFilename = (filename: string) => {
    // Remove hash prefix pattern: {hash}_{filename} -> {filename}
    if (filename.includes('_')) {
      const parts = filename.split('_');
      // Check if first part looks like a hash (8+ chars, alphanumeric/hex)
      if (parts[0].length >= 8 && /^[a-f0-9]+$/i.test(parts[0])) {
        return parts.slice(1).join('_');
      }
    }
    return filename;
  };

  // Group citations by document to show unique sources with citation numbers
  const uniqueSources = citations.reduce((acc, citation, idx) => {
    const cleanTitle = cleanFilename(citation.title);
    const key = cleanTitle;
    if (!acc[key]) {
      acc[key] = {
        title: cleanTitle,
        pages: new Set<number>(),
        maxScore: citation.score,
        doc_id: citation.doc_id,
        metadata: citation.metadata,
        citationNumbers: []
      };
    }
    if (citation.page) {
      acc[key].pages.add(citation.page);
    }
    acc[key].maxScore = Math.max(acc[key].maxScore, citation.score);
    acc[key].citationNumbers.push(idx + 1); // Track citation number (1-indexed)
    return acc;
  }, {} as Record<string, { title: string; pages: Set<number>; maxScore: number; doc_id: string; metadata?: { source_url?: string; storage_type?: string; [key: string]: unknown }; citationNumbers: number[] }>);

  const sources = Object.values(uniqueSources).map(source => ({
    title: source.title,
    pages: Array.from(source.pages).sort((a, b) => a - b),
    score: source.maxScore,
    doc_id: source.doc_id,
    metadata: source.metadata,
    citationNumbers: source.citationNumbers
  }));

  const getCompletenessColor = () => {
    if (completeness_check.is_complete) return 'border-green-200 bg-green-50';
    if (completeness_check.completeness > 0.6) return 'border-yellow-200 bg-yellow-50';
    return 'border-red-200 bg-red-50';
  };

  const getCompletenessIcon = () => {
    if (completeness_check.is_complete) 
      return <CheckCircle className="w-5 h-5 text-green-600" />;
    if (completeness_check.completeness > 0.6) 
      return <AlertCircle className="w-5 h-5 text-yellow-600" />;
    return <XCircle className="w-5 h-5 text-red-600" />;
  };

  const getCompletenessLabel = () => {
    if (completeness_check.is_complete) return 'Complete Answer';
    if (completeness_check.completeness > 0.6) return 'Partially Complete';
    return 'Incomplete Information';
  };

  return (
    <div className="w-full space-y-6">
      {/* Question Echo */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm font-medium text-blue-900">Question:</p>
        <p className="text-gray-800 mt-1">{question}</p>
      </div>

      {/* Answer Section */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <h3 className="text-lg font-semibold mb-3 text-gray-900">Answer</h3>
        <div className="prose prose-sm max-w-none">
          <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">{answer}</p>
        </div>
      </div>

      {/* Completeness Check */}
      <div className={`border-2 rounded-lg p-5 ${getCompletenessColor()}`}>
        <div className="flex items-start gap-3">
          {getCompletenessIcon()}
          <div className="flex-1">
            <h4 className="font-semibold mb-3 text-gray-900">
              {getCompletenessLabel()}
            </h4>
            
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-white bg-opacity-50 p-3 rounded">
                <span className="text-xs font-medium text-gray-600 block mb-1">Confidence</span>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 h-2 rounded-full overflow-hidden">
                    <div 
                      className="bg-blue-500 h-full transition-all"
                      style={{ width: `${completeness_check.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-bold text-gray-900">
                    {(completeness_check.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
              
              <div className="bg-white bg-opacity-50 p-3 rounded">
                <span className="text-xs font-medium text-gray-600 block mb-1">Completeness</span>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 h-2 rounded-full overflow-hidden">
                    <div 
                      className="bg-green-500 h-full transition-all"
                      style={{ width: `${completeness_check.completeness * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-bold text-gray-900">
                    {(completeness_check.completeness * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>

            {completeness_check.missing_information && (
              <div className="mb-4 p-3 bg-white bg-opacity-70 rounded border border-gray-200">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-orange-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-gray-900 mb-1">Missing Information:</p>
                    <p className="text-sm text-gray-700">{completeness_check.missing_information}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Enrichment Suggestions */}
            {(completeness_check.suggested_documents.length > 0 || 
              completeness_check.suggested_actions.length > 0) && (
              <div className="space-y-3">
                <h5 className="text-sm font-semibold text-gray-900">💡 Enrichment Suggestions:</h5>
                
                {completeness_check.suggested_documents.length > 0 && (
                  <div className="bg-white bg-opacity-70 p-3 rounded border border-gray-200">
                    <p className="text-xs font-medium text-gray-600 mb-2">Suggested Documents to Add:</p>
                    <ul className="text-sm text-gray-800 space-y-1">
                      {completeness_check.suggested_documents.map((doc, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-blue-600 mt-0.5">•</span>
                          <span>{doc}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {completeness_check.suggested_actions.length > 0 && (
                  <div className="bg-white bg-opacity-70 p-3 rounded border border-gray-200">
                    <p className="text-xs font-medium text-gray-600 mb-2">Suggested Actions:</p>
                    <ul className="text-sm text-gray-800 space-y-1">
                      {completeness_check.suggested_actions.map((action, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-green-600 mt-0.5">→</span>
                          <span>{action}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Auto-Enrichment Results */}
      {enrichment_data && enrichment_data.enrichment_performed && enrichment_data.sources_found.length > 0 && (
        <div className="bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-purple-200 rounded-lg p-5">
          <div className="flex items-start gap-3">
            <Sparkles className="w-6 h-6 text-purple-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="font-semibold text-purple-900 mb-2 flex items-center gap-2">
                Auto-Enrichment: External Sources Found
              </h4>
              <p className="text-sm text-purple-700 mb-4">{enrichment_data.message}</p>
              
              {enrichment_data.search_terms.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs font-medium text-purple-600 mb-1">Search Terms Used:</p>
                  <div className="flex flex-wrap gap-2">
                    {enrichment_data.search_terms.map((term, idx) => (
                      <span key={idx} className="px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded-full">
                        {term}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-3">
                <p className="text-xs font-medium text-purple-600 mb-2">Recommended Sources to Add:</p>
                {enrichment_data.sources_found.map((source, idx) => {
                  const urlState = urlStates[source.url] || {
                    isAdding: false,
                    added: false,
                    error: null,
                    alreadyExists: false
                  };

                  return (
                    <div key={idx} className="bg-white p-4 rounded-lg border border-purple-200 hover:border-purple-400 transition-colors">
                      <div className="flex flex-col gap-3">
                        {/* Header with badge and button */}
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full font-medium whitespace-nowrap">
                              {source.source}
                            </span>
                          </div>
                          
                          {/* Add to KB Button */}
                          <div className="flex-shrink-0">
                            {urlState.alreadyExists || urlState.added ? (
                              <div className="flex items-center gap-1 px-3 py-1.5 bg-green-50 text-green-700 text-xs rounded-full font-medium whitespace-nowrap">
                                <Check className="w-3 h-3" />
                                <span>In KB</span>
                              </div>
                            ) : urlState.error ? (
                              <button
                                onClick={() => handleAddToKB(source.url, source.title)}
                                className="flex items-center gap-1 px-3 py-1.5 bg-red-50 text-red-700 text-xs rounded-full font-medium hover:bg-red-100 transition-colors whitespace-nowrap"
                                title={urlState.error}
                              >
                                <Plus className="w-3 h-3" />
                                <span>Retry</span>
                              </button>
                            ) : (
                              <button
                                onClick={() => handleAddToKB(source.url, source.title)}
                                disabled={urlState.isAdding}
                                className="flex items-center gap-1 px-3 py-1.5 bg-purple-600 text-white text-xs rounded-full font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
                              >
                                {urlState.isAdding ? (
                                  <>
                                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    <span>Adding...</span>
                                  </>
                                ) : (
                                  <>
                                    <Plus className="w-3 h-3" />
                                    <span>Add to KB</span>
                                  </>
                                )}
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Title and link */}
                        <div>
                          <a 
                            href={source.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-purple-900 hover:text-purple-700 hover:underline inline-flex items-center gap-1.5 group"
                          >
                            <span className="break-words">{source.title}</span>
                            <ExternalLink className="w-3.5 h-3.5 flex-shrink-0 group-hover:translate-x-0.5 transition-transform" />
                          </a>
                        </div>

                        {/* Summary - only show if it's clean text */}
                        {source.summary && 
                         !source.summary.includes('data:image') && 
                         !source.summary.includes('https://') && 
                         !source.summary.includes('http://') &&
                         !source.summary.match(/[{}\[\]<>]/g) &&
                         source.summary.length > 20 && 
                         source.summary.length < 300 && (
                          <p className="text-xs text-gray-600 leading-relaxed line-clamp-2">
                            {source.summary}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Citations */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-5">
        <div className="flex items-center gap-2 mb-4">
          <BookOpen className="w-5 h-5 text-gray-600" />
          <h4 className="font-semibold text-gray-800">
            Sources ({sources.length})
          </h4>
        </div>
        <div className="space-y-3">
          {sources.map((source, idx) => {
            const citationWithMeta = citations.find(c => cleanFilename(c.title) === source.title);
            const sourceUrl = citationWithMeta?.metadata?.source_url;
            
            return (
              <div key={idx} className="bg-white p-4 rounded border border-gray-200 hover:border-blue-300 transition-colors">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-700 rounded-full text-center text-sm font-semibold leading-7">
                      {idx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      {sourceUrl ? (
                        <a 
                          href={sourceUrl} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline truncate block"
                          title={`Visit: ${sourceUrl}`}
                        >
                          {source.title}
                        </a>
                      ) : (
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {source.title}
                        </p>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        {/* Citation numbers */}
                        <div className="flex flex-wrap gap-1">
                          {source.citationNumbers?.map((num) => (
                            <span key={num} className="text-xs font-mono bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                              [{num}]
                            </span>
                          ))}
                        </div>
                        {/* Pages */}
                        {source.pages.length > 0 && (
                          <p className="text-xs text-gray-600">
                            {source.pages.length === 1 
                              ? `• Page ${source.pages[0]}`
                              : `• Pages ${source.pages.join(', ')}`
                            }
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded font-medium">
                      {(source.score * 100).toFixed(0)}% match
                    </span>
                    
                    {/* View PDF Button - show for all PDFs */}
                    {source.title.toLowerCase().endsWith('.pdf') && (
                      <button
                        onClick={async () => {
                          try {
                            const result = await api.getPdfUrl(source.doc_id);
                            window.open(result.url, '_blank');
                          } catch (error) {
                            console.error('Failed to get PDF URL:', error);
                            // Fallback to source URL if available
                            if (sourceUrl) {
                              window.open(sourceUrl, '_blank');
                            } else {
                              alert('Failed to open PDF');
                            }
                          }
                        }}
                        className="flex items-center gap-1 px-2 py-1 text-xs text-purple-600 hover:text-purple-800 hover:bg-purple-50 rounded transition-colors"
                        title="View PDF"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>View PDF</span>
                      </button>
                    )}
                    
                    {/* Open Document Button for non-PDF web sources */}
                    {!source.title.toLowerCase().endsWith('.pdf') && sourceUrl && (
                      <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded transition-colors"
                        title="Open source"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>Open</span>
                      </a>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Metadata */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Clock className="w-4 h-4" />
          <span>Response time: {latency_ms.toFixed(0)}ms</span>
        </div>

        {/* Rating Section */}
        <div className="flex items-center gap-3">
          {!userRating && !submitMessage && (
            <>
              <span className="text-sm text-gray-600">Was this helpful?</span>
              <button
                onClick={() => handleRating('up')}
                className="p-2 rounded-lg hover:bg-green-50 transition-colors group"
                title="Helpful"
              >
                <ThumbsUp className="w-5 h-5 text-gray-400 group-hover:text-green-600" />
              </button>
              <button
                onClick={() => handleRating('down')}
                className="p-2 rounded-lg hover:bg-red-50 transition-colors group"
                title="Not helpful"
              >
                <ThumbsDown className="w-5 h-5 text-gray-400 group-hover:text-red-600" />
              </button>
            </>
          )}

          {userRating && !submitMessage && (
            <div className="flex items-center gap-2">
              {userRating === 'up' ? (
                <ThumbsUp className="w-5 h-5 text-green-600" />
              ) : (
                <ThumbsDown className="w-5 h-5 text-red-600" />
              )}
              <span className="text-sm text-gray-600">
                {userRating === 'up' ? 'Helpful!' : 'Thanks for feedback'}
              </span>
            </div>
          )}

          {submitMessage && (
            <span className="text-sm text-green-600">{submitMessage}</span>
          )}
        </div>
      </div>

      {/* Optional Feedback Text Area */}
      {showFeedback && !submitMessage && (
        <div className="mt-4 p-4 bg-white rounded-lg border-2 border-blue-200 shadow-sm">
          <label className="block text-sm font-medium text-gray-900 mb-2">
            Help us improve (optional):
          </label>
          <textarea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="What could we do better?"
            className="w-full px-3 py-2 bg-white border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 placeholder-gray-400 resize-none"
            rows={3}
          />
          <div className="flex gap-2 mt-3">
            <button
              onClick={submitRating}
              disabled={isSubmitting}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
            </button>
            <button
              onClick={() => {
                setShowFeedback(false);
                submitRating();
              }}
              disabled={isSubmitting}
              className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              Skip
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

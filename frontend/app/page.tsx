'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Header from '@/components/Header';
import ProtectedRoute from '@/components/ProtectedRoute';
import FileUpload from '@/components/FileUpload';
import QuestionInput from '@/components/QuestionInput';
import AnswerCard from '@/components/AnswerCard';
import { api, DocumentUploadResponse, AskResponse, KnowledgeBaseDocument } from '@/lib/api';
import { Brain, Database, Clock, FileText, Globe, ExternalLink } from 'lucide-react';

export default function Home() {
  const [uploadedDocs, setUploadedDocs] = useState<DocumentUploadResponse[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [recentDocs, setRecentDocs] = useState<KnowledgeBaseDocument[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(true);

  // Helper function to remove hash prefix from document names
  const cleanDocumentName = (title: string): string => {
    // Remove hash prefix like "3b6bace73e9d3997_" from filenames
    return title.replace(/^[a-f0-9]{8,}_/i, '');
  };

  useEffect(() => {
    loadRecentDocuments();
  }, []);

  const loadRecentDocuments = async () => {
    try {
      setLoadingRecent(true);
      const response = await api.listDocuments();
      setRecentDocs(response.documents.slice(0, 5)); // Get 5 most recent
    } catch (error) {
      console.error('Failed to load recent documents:', error);
    } finally {
      setLoadingRecent(false);
    }
  };

  const handleUploadComplete = (docs: DocumentUploadResponse[]) => {
    setUploadedDocs((prev) => [...prev, ...docs]);
    loadRecentDocuments(); // Refresh recent docs
  };

  const handleAsk = async (question: string) => {
    setIsAsking(true);
    setResult(null);

    try {
      const response = await api.askQuestion(question);
      setResult(response);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to get answer';
      alert(message);
    } finally {
      setIsAsking(false);
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Recently added';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'Recently added';
    }
  };

  return (
    <ProtectedRoute>
      <main className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-gray-100">
        {/* Header */}
        <Header />

        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Sidebar - Knowledge Base */}
            <div className="lg:col-span-1">
              <div className="sticky top-24 space-y-6">
                {/* Upload Section */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Database className="w-5 h-5 text-blue-600" />
                  <h2 className="text-lg font-semibold text-gray-900">
                    Knowledge Base
                  </h2>
                </div>
                <FileUpload onUploadComplete={handleUploadComplete} />
              </div>

              {/* Recent Documents */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-900">Recently Added</h3>
                  <Link 
                    href="/knowledge-base"
                    className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                  >
                    View All
                  </Link>
                </div>
                
                {loadingRecent ? (
                  <div className="flex justify-center py-4">
                    <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : recentDocs.length === 0 ? (
                  <p className="text-xs text-gray-500 text-center py-4">
                    No documents yet
                  </p>
                ) : (
                  <div className="space-y-2">
                    {recentDocs.map((doc) => (
                      <div
                        key={doc.doc_id}
                        className="group p-3 rounded-lg border border-gray-100 hover:border-blue-200 hover:bg-blue-50 transition-colors"
                      >
                        <div className="flex items-start gap-2">
                          {doc.source_type === 'web' ? (
                            <Globe className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
                          ) : (
                            <FileText className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">
                              {cleanDocumentName(doc.title)}
                            </p>
                            <p className="text-xs text-gray-500 mt-0.5">
                              {formatDate(doc.added_at)}
                            </p>
                          </div>
                          
                          {/* View PDF for S3 */}
                          {doc.storage_type === 's3' && (
                            <button
                              onClick={async (e) => {
                                e.stopPropagation();
                                try {
                                  const result = await api.getPdfUrl(doc.doc_id);
                                  window.open(result.url, '_blank');
                                } catch {
                                  alert('Failed to open PDF');
                                }
                              }}
                              className="opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <ExternalLink className="w-3 h-3 text-purple-600" />
                            </button>
                          )}
                          
                          {/* Open web source */}
                          {doc.source_url && doc.storage_type !== 's3' && (
                            <a
                              href={doc.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <ExternalLink className="w-3 h-3 text-blue-600" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Main Content - Q&A */}
          <div className="lg:col-span-2 space-y-6">
            {/* Question Input */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold mb-4 text-gray-900">
                Ask a Question
              </h2>
              <QuestionInput 
                onAsk={handleAsk} 
                isLoading={isAsking}
              />
              <p className="text-sm text-gray-500 mt-3">
                💡 Ask anything! Auto-enrichment will find external sources if needed
              </p>
            </div>

            {/* Answer Display */}
            {result && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h2 className="text-lg font-semibold mb-4 text-gray-900">
                  AI Response
                </h2>
                <AnswerCard result={result} />
              </div>
            )}

            {/* Empty State */}
            {!result && !isAsking && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
                <div className="max-w-sm mx-auto">
                  <Brain className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    Ready to Answer
                  </h3>
                  <p className="text-sm text-gray-600">
                    Ask a question above to search through your knowledge base.
                    If we don&apos;t have the answer, auto-enrichment will find external sources.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
    </ProtectedRoute>
  );
}

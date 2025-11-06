'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Header from '@/components/Header';
import ProtectedRoute from '@/components/ProtectedRoute';
import { api, KnowledgeBaseDocument } from '@/lib/api';
import { FileText, Globe, Upload, ExternalLink, Trash2, Calendar, Database, ArrowLeft } from 'lucide-react';

export default function KnowledgeBasePage() {
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'upload' | 'web'>('all');

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.listDocuments();
      setDocuments(response.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await api.deleteDocument(docId);
      setDocuments(docs => docs.filter(d => d.doc_id !== docId));
    } catch (err) {
      alert('Failed to delete document');
    }
  };

  const handleOpen = (doc: KnowledgeBaseDocument) => {
    if (doc.source_url) {
      window.open(doc.source_url, '_blank');
    } else if (doc.storage_type === 'local') {
      alert('This document is stored locally and cannot be opened in the browser.');
    }
  };

  // Helper function to remove hash prefix from document names
  const cleanDocumentName = (title: string): string => {
    // Remove hash prefix like "3b6bace73e9d3997_" from filenames
    return title.replace(/^[a-f0-9]{8,}_/i, '');
  };

  const filteredDocs = documents.filter(doc => {
    if (filter === 'all') return true;
    return doc.source_type === filter;
  });

  const getIcon = (sourceType: string) => {
    switch (sourceType) {
      case 'web':
        return <Globe className="w-5 h-5 text-blue-600" />;
      case 'upload':
        return <Upload className="w-5 h-5 text-green-600" />;
      default:
        return <FileText className="w-5 h-5 text-gray-600" />;
    }
  };

  const getTypeLabel = (sourceType: string) => {
    switch (sourceType) {
      case 'web':
        return 'Web Source';
      case 'upload':
        return 'Uploaded File';
      default:
        return 'Document';
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Unknown date';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'Unknown date';
    }
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
        <Header />
        <div className="max-w-7xl mx-auto p-8">
          {/* Page Title */}
          <div className="mb-8">
            <Link 
            href="/"
            className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 mb-4 font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Search</span>
          </Link>
          
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-4xl font-bold text-gray-900 mb-2">Knowledge Base</h1>
              <p className="text-gray-600">Manage your documents and web sources</p>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg border border-gray-200 shadow-sm">
              <Database className="w-5 h-5 text-blue-600" />
              <span className="text-sm font-medium text-gray-700">
                {filteredDocs.length} {filteredDocs.length === 1 ? 'Document' : 'Documents'}
              </span>
            </div>
          </div>

          {/* Filters */}
          <div className="flex gap-2">
            <button
              onClick={() => setFilter('all')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                filter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              All ({documents.length})
            </button>
            <button
              onClick={() => setFilter('upload')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                filter === 'upload'
                  ? 'bg-green-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              Uploaded ({documents.filter(d => d.source_type === 'upload').length})
            </button>
            <button
              onClick={() => setFilter('web')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                filter === 'web'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              Web Sources ({documents.filter(d => d.source_type === 'web').length})
            </button>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <p className="text-red-800">{error}</p>
            <button
              onClick={loadDocuments}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              Retry
            </button>
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
            <Database className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">No documents found</h3>
            <p className="text-gray-600">
              {filter === 'all'
                ? 'Upload documents or add web sources to get started.'
                : `No ${filter === 'upload' ? 'uploaded files' : 'web sources'} in your knowledge base.`}
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            {filteredDocs.map((doc) => (
              <div
                key={doc.doc_id}
                className="bg-white border border-gray-200 rounded-lg p-6 hover:border-blue-300 hover:shadow-md transition-all"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4 flex-1 min-w-0">
                    {/* Icon */}
                    <div className="flex-shrink-0 mt-1">
                      {getIcon(doc.source_type)}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-lg font-semibold text-gray-900 truncate mr-2">
                          {cleanDocumentName(doc.title)}
                        </h3>
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded-full font-medium">
                          {getTypeLabel(doc.source_type)}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
                        <div className="flex items-center gap-1">
                          <Calendar className="w-4 h-4" />
                          <span>{formatDate(doc.added_at)}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <FileText className="w-4 h-4" />
                          <span>{doc.chunk_count} chunks</span>
                        </div>
                        {doc.source_url && (
                          <div className="flex items-center gap-1 text-blue-600 truncate max-w-md">
                            <Globe className="w-4 h-4 flex-shrink-0" />
                            <span className="truncate">{doc.source_url}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {/* View PDF button for S3 PDFs */}
                    {doc.storage_type === 's3' && (
                      <button
                        onClick={async () => {
                          try {
                            const result = await api.getPdfUrl(doc.doc_id);
                            window.open(result.url, '_blank');
                          } catch {
                            alert('Failed to open PDF');
                          }
                        }}
                        className="flex items-center gap-1 px-3 py-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                        title="View PDF from S3"
                      >
                        <ExternalLink className="w-4 h-4" />
                        <span className="text-sm font-medium">View PDF</span>
                      </button>
                    )}
                    
                    {/* Open source for web URLs */}
                    {doc.source_url && doc.storage_type !== 's3' ? (
                      <button
                        onClick={() => handleOpen(doc)}
                        className="flex items-center gap-1 px-3 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                        title="Open source"
                      >
                        <ExternalLink className="w-4 h-4" />
                        <span className="text-sm font-medium">Open</span>
                      </button>
                    ) : doc.storage_type === 'local' ? (
                      <span className="px-3 py-2 text-gray-400 text-sm">
                        📁 Local File
                      </span>
                    ) : null}
                    
                    <button
                      onClick={() => handleDelete(doc.doc_id)}
                      className="flex items-center gap-1 px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="Delete document"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
    </ProtectedRoute>
  );
}

'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, Loader2, CheckCircle, X } from 'lucide-react';
import { api, DocumentUploadResponse } from '@/lib/api';

interface FileUploadProps {
  onUploadComplete: (docs: DocumentUploadResponse[]) => void;
}

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [uploadedDocs, setUploadedDocs] = useState<DocumentUploadResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[], rejectedFiles: any[]) => {
    setError(null);
    
    // Handle rejected files
    if (rejectedFiles.length > 0) {
      const errors = rejectedFiles.map(f => {
        if (f.errors[0]?.code === 'file-too-large') {
          return `${f.file.name}: File too large (max 50MB)`;
        }
        if (f.errors[0]?.code === 'file-invalid-type') {
          return `${f.file.name}: Invalid file type (only PDF, DOCX, TXT allowed)`;
        }
        return `${f.file.name}: ${f.errors[0]?.message}`;
      });
      setError(errors.join('\n'));
      return;
    }
    
    if (acceptedFiles.length === 0) return;

    setUploading(true);
    try {
      const docs = await api.uploadDocuments(acceptedFiles);
      
      // Auto-ingest all uploaded documents
      setIngesting(true);
      for (const doc of docs) {
        await api.ingestDocument(doc.doc_id);
      }
      setIngesting(false);

      setUploadedDocs((prev) => [...prev, ...docs]);
      onUploadComplete(docs);
    } catch (error: any) {
      console.error('Upload/Ingest error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to upload or ingest documents';
      setError(errorMessage);
    } finally {
      setUploading(false);
      setIngesting(false);
    }
  }, [onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'text/plain': ['.txt'],
    },
    maxSize: 50 * 1024 * 1024, // 50MB
    multiple: true,
  });

  const removeDoc = async (docId: string) => {
    try {
      await api.deleteDocument(docId);
      setUploadedDocs(prev => prev.filter(doc => doc.doc_id !== docId));
    } catch (error) {
      console.error('Delete error:', error);
      alert('Failed to delete document');
    }
  };

  return (
    <div className="w-full space-y-4">
      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <X className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800">Upload Error</p>
              <p className="text-sm text-red-700 mt-1 whitespace-pre-line">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-700"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
      
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-blue-400 bg-white'
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          {uploading || ingesting ? (
            <>
              <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
              <p className="text-sm font-medium text-gray-700">
                {uploading ? 'Uploading...' : 'Processing documents...'}
              </p>
            </>
          ) : (
            <>
              <Upload className="w-10 h-10 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-gray-700">
                  {isDragActive ? 'Drop files here' : 'Drag & drop documents here'}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  or click to browse • PDF, DOCX, TXT • Max 50MB
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {uploadedDocs.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-gray-700">
            Knowledge Base ({uploadedDocs.length} {uploadedDocs.length === 1 ? 'document' : 'documents'})
          </h3>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {uploadedDocs.map((doc) => (
              <div
                key={doc.doc_id}
                className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200"
              >
                <FileText className="w-5 h-5 text-blue-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {doc.filename}
                  </p>
                  <p className="text-xs text-gray-500">
                    {(doc.size_bytes / 1024).toFixed(1)} KB
                  </p>
                </div>
                <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                <button
                  onClick={() => removeDoc(doc.doc_id)}
                  className="p-1 hover:bg-gray-200 rounded transition-colors"
                  title="Remove from view"
                >
                  <X className="w-4 h-4 text-gray-500" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

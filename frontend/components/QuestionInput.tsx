'use client';

import { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';

interface QuestionInputProps {
  onAsk: (question: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export default function QuestionInput({ onAsk, isLoading, disabled }: QuestionInputProps) {
  const [question, setQuestion] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim() && !isLoading && !disabled) {
      onAsk(question.trim());
      setQuestion(''); // Clear input after asking
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your documents..."
            className="w-full px-4 py-3 pr-12 bg-white border-2 border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed"
            disabled={isLoading || disabled}
          />
          <Search className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        </div>
        <button
          type="submit"
          disabled={isLoading || !question.trim() || disabled}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors flex items-center gap-2 shadow-sm"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Thinking...
            </>
          ) : (
            'Ask'
          )}
        </button>
      </div>
    </form>
  );
}

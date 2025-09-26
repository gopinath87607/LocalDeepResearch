import React, { useState, useRef, useEffect } from 'react';
import { useDeepResearch } from '../hooks/useDeepResearch';
import { Search, CheckCircle, MessageSquare, Trash2, Copy, Download, Zap, Brain, Server, Activity, Link, ExternalLink, Send, MessageCircle, User, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const DeepResearchDashboard = () => {
  const [query, setQuery] = useState('');
  const [copied, setCopied] = useState({});
  const [chatInput, setChatInput] = useState('');
  
  const {
    startResearch,
    isResearching,
    currentStep,
    researchSteps,
    finalResult,
    progress,
    error,
    groupedLogs,
    clearLogs,
    websiteLinks,
    clearWebsiteLinks,
    isChatReady,
    chatMessages,
    isChatLoading,
    sendChatMessage,
    clearChat
  } = useDeepResearch();

  // Refs for auto-scroll
  const serverLogRef = useRef(null);
  const researchLogRef = useRef(null);
  const linksRef = useRef(null);
  const chatRef = useRef(null);

  // Auto-scroll effects
  useEffect(() => {
    if (serverLogRef.current) {
      serverLogRef.current.scrollTop = serverLogRef.current.scrollHeight;
    }
  }, [groupedLogs]);

  useEffect(() => {
    if (researchLogRef.current) {
      researchLogRef.current.scrollTop = researchLogRef.current.scrollHeight;
    }
  }, [groupedLogs]);

  useEffect(() => {
    if (linksRef.current) {
      linksRef.current.scrollTop = linksRef.current.scrollHeight;
    }
  }, [websiteLinks]);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [chatMessages]);

  // Show chat automatically when ready
  useEffect(() => {
    if (isChatReady) {
      // Auto-scroll to results section when chat becomes ready
      setTimeout(() => {
        const resultsSection = document.querySelector('[data-results-section]');
        if (resultsSection) {
          resultsSection.scrollIntoView({ behavior: 'smooth' });
        }
      }, 500);
    }
  }, [isChatReady]);

  const handleSubmit = () => {
    if (query.trim() && !isResearching) {
      startResearch(query.trim());
    }
  };

  const handleChatSubmit = () => {
    if (chatInput.trim() && !isChatLoading) {
      sendChatMessage(chatInput);
      setChatInput('');
    }
  };

  const handleChatKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleChatSubmit();
    }
  };

  const handleCopy = async (content, key) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(prev => ({ ...prev, [key]: true }));
      setTimeout(() => setCopied(prev => ({ ...prev, [key]: false })), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleClearWebsiteLinks = () => {
    clearWebsiteLinks();
  };

  const copyAllLinks = async () => {
    const linkList = websiteLinks.map(link => link.url).join('\n');
    await handleCopy(linkList, 'all-links');
  };

  // FIXED: Better separation - misc for server, everything else for research
  const miscLogs = groupedLogs.filter(g => g.round === 'misc').flatMap(g => g.items) || [];
  const researchLogs = groupedLogs.filter(g => g.round !== 'misc').flatMap(g => g.items) || [];

  const LogEntry = ({ log, index, isResearch = false }) => {
    let icon, bgColor, borderColor, typeLabel;
    
    if (isResearch) {
      switch (log.type) {
        case 'react_thought':
          icon = <Brain className="w-4 h-4 text-blue-600" />;
          bgColor = 'bg-blue-50';
          borderColor = 'border-l-blue-500';
          typeLabel = 'Thinking';
          break;
        case 'react_action':
          icon = <Activity className="w-4 h-4 text-purple-600" />;
          bgColor = 'bg-purple-50';
          borderColor = 'border-l-purple-500';
          typeLabel = 'Action';
          break;
        case 'llm_prompt':
          icon = <Zap className="w-4 h-4 text-green-600" />;
          bgColor = 'bg-green-50';
          borderColor = 'border-l-green-500';
          typeLabel = 'LLM Call';
          break;
        case 'research_details':
          icon = <CheckCircle className="w-4 h-4 text-indigo-600" />;
          bgColor = 'bg-indigo-50';
          borderColor = 'border-l-indigo-500';
          typeLabel = 'Complete';
          break;
        default:
          icon = <MessageSquare className="w-4 h-4 text-gray-600" />;
          bgColor = 'bg-gray-50';
          borderColor = 'border-l-gray-400';
          typeLabel = 'Research';
      }
    } else {
      icon = <Server className="w-4 h-4 text-gray-600" />;
      bgColor = 'bg-gray-50';
      borderColor = 'border-l-gray-400';
      typeLabel = 'Server';
    }

    return (
      <div key={index} className={`mb-3 p-3 rounded-lg ${bgColor} border-l-4 ${borderColor} transition-all duration-200 hover:shadow-sm`}>
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">{icon}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-gray-700">{typeLabel}</span>
              <span className="text-xs text-gray-500 bg-white px-2 py-0.5 rounded-full">{log.timestamp}</span>
            </div>
            <div className="text-sm text-gray-800 leading-relaxed bg-white p-2 rounded border font-mono whitespace-pre-wrap">
              {log.content}
            </div>
            {isResearch && log.type === 'llm_prompt' && (
              <div className="mt-2 text-xs text-blue-700 bg-blue-100 px-2 py-1 rounded-full inline-block">
                Est. Tokens: {Math.ceil(log.content.length / 4)}
              </div>
            )}
          </div>
          <button
            onClick={() => handleCopy(log.content, `log-${index}`)}
            className="flex-shrink-0 p-1.5 text-gray-400 hover:text-gray-700 hover:bg-white rounded transition-colors"
            title="Copy"
          >
            <Copy className="w-3 h-3" />
          </button>
        </div>
        {copied[`log-${index}`] && (
          <div className="text-xs text-green-600 text-center mt-1 font-medium">Copied!</div>
        )}
      </div>
    );
  };

  const LinkEntry = ({ link, index }) => {
    const handleLinkCopy = () => handleCopy(link.url, `link-${index}`);
    
    const getSourceColor = (source) => {
      switch (source) {
        case 'url_visited': return 'text-green-600 bg-green-100';
        case 'url_found': return 'text-blue-600 bg-blue-100';
        case 'search_result': return 'text-purple-600 bg-purple-100';
        case 'react_action': return 'text-orange-600 bg-orange-100';
        default: return 'text-gray-600 bg-gray-100';
      }
    };

    const getSourceLabel = (source) => {
      switch (source) {
        case 'url_visited': return 'Visited';
        case 'url_found': return 'Found';
        case 'search_result': return 'Search';
        case 'react_action': return 'Action';
        default: return 'Other';
      }
    };

    return (
      <div key={link.id} className="mb-3 p-3 rounded-lg bg-orange-50 border-l-4 border-l-orange-500 transition-all duration-200 hover:shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            <Link className="w-4 h-4 text-orange-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-gray-700">
                {link.domain || link.displayName || 'Website'}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${getSourceColor(link.source)}`}>
                {getSourceLabel(link.source)}
              </span>
              <span className="text-xs text-gray-500 bg-white px-2 py-0.5 rounded-full">{link.timestamp}</span>
            </div>
            <div className="text-sm text-gray-800 leading-relaxed bg-white p-2 rounded border">
              <a 
                href={link.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 hover:underline break-all flex items-center gap-1"
              >
                {link.url}
                <ExternalLink className="w-3 h-3 flex-shrink-0" />
              </a>
            </div>
            {link.goal && (
              <div className="mt-2 text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded">
                Purpose: {link.goal}
              </div>
            )}
          </div>
          <button
            onClick={handleLinkCopy}
            className="flex-shrink-0 p-1.5 text-gray-400 hover:text-gray-700 hover:bg-white rounded transition-colors"
            title="Copy URL"
          >
            <Copy className="w-3 h-3" />
          </button>
        </div>
        {copied[`link-${index}`] && (
          <div className="text-xs text-green-600 text-center mt-1 font-medium">URL Copied!</div>
        )}
      </div>
    );
  };

  const ChatMessage = ({ message, index }) => {
    const isUser = message.role === 'user';
    const isSystem = message.role === 'system';
    
    if (isSystem) {
      return (
        <div key={index} className="flex justify-center my-4">
          <div className="bg-green-100 text-green-800 px-4 py-2 rounded-full text-sm font-medium flex items-center gap-2">
            <MessageCircle className="w-4 h-4" />
            {message.content}
          </div>
        </div>
      );
    }
    
    return (
      <div key={index} className={`mb-4 flex ${isUser ? 'justify-end' : 'justify-start'}`}>
        <div className={`max-w-[80%] ${isUser ? 'order-2' : 'order-1'}`}>
          <div className={`flex items-end gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              isUser ? 'bg-blue-500 text-white' : 'bg-gray-500 text-white'
            }`}>
              {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div className={`px-4 py-2 rounded-lg max-w-full ${
              isUser 
                ? 'bg-blue-500 text-white rounded-br-sm' 
                : 'bg-gray-100 text-gray-800 rounded-bl-sm'
            }`}>
              <div className="text-sm leading-relaxed">
                {isUser ? (
                  message.content
                ) : (
                  <ReactMarkdown 
                    components={{
                      p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
                      strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                      code: ({children}) => <code className="bg-gray-200 px-1 py-0.5 rounded text-xs">{children}</code>,
                      ul: ({children}) => <ul className="list-disc list-inside mb-2">{children}</ul>,
                      ol: ({children}) => <ol className="list-decimal list-inside mb-2">{children}</ol>,
                      li: ({children}) => <li className="mb-1">{children}</li>,
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                )}
              </div>
              <div className={`text-xs mt-1 ${isUser ? 'text-blue-100' : 'text-gray-500'}`}>
                {message.timestamp}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Google-Style Header */}
      <div className="bg-white shadow-sm">
        <div className="max-w-4xl mx-auto px-6 py-8">
          <div className="text-center">
            <h1 className="text-5xl font-light text-gray-900 mb-8">
              Deep<span className="text-blue-500">Research</span>
            </h1>
            
            {/* Search Bar */}
            <div className="max-w-xl mx-auto mb-6">
              <div className="flex rounded-full border border-gray-300 shadow-lg hover:shadow-xl transition-shadow bg-white">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask me anything to research..."
                  className="flex-1 px-6 py-4 text-lg rounded-l-full border-none focus:outline-none focus:ring-0"
                  disabled={isResearching}
                  onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
                />
                <button
                  onClick={handleSubmit}
                  disabled={isResearching || !query.trim()}
                  className="px-6 py-4 bg-blue-500 text-white rounded-r-full hover:bg-blue-600 disabled:bg-gray-400 flex items-center gap-2 font-medium transition-colors"
                >
                  <Search className="w-5 h-5" />
                  {isResearching ? 'Researching...' : 'Research'}
                </button>
              </div>
            </div>

            {/* Progress Bar */}
            {isResearching && (
              <div className="max-w-xl mx-auto">
                <div className="bg-gray-200 rounded-full h-2 mb-2">
                  <div 
                    className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="text-sm text-gray-600">{currentStep}</p>
              </div>
            )}

            {/* Chat Ready Notification */}
            {isChatReady && (
              <div className="max-w-xl mx-auto mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center justify-center gap-2 text-green-700">
                  <MessageCircle className="w-5 h-5" />
                  <span>Chat is ready! Scroll down to ask follow-up questions about your research.</span>
                </div>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="max-w-xl mx-auto mt-4 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                Error: {error}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Three-Column Log Boxes */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          
          {/* Left: Server Logs */}
          <div className="bg-white rounded-lg shadow-md border">
            <div className="bg-gray-100 px-4 py-3 border-b flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <Server className="w-5 h-5" />
                Server & System Logs
              </h2>
              {miscLogs.length > 0 && (
                <button 
                  onClick={clearLogs}
                  className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1 px-2 py-1 rounded hover:bg-red-50"
                >
                  <Trash2 className="w-4 h-4" />
                  Clear
                </button>
              )}
            </div>
            
            <div className="p-4 h-80 overflow-y-auto" ref={serverLogRef}>
              {miscLogs.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Server className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                  <p className="italic">No server logs yet...</p>
                </div>
              ) : (
                miscLogs.map((log, index) => (
                  <LogEntry key={`server-${index}`} log={log} index={`server-${index}`} isResearch={false} />
                ))
              )}
            </div>
          </div>

          {/* Center: Research Logs */}
          <div className="bg-white rounded-lg shadow-md border">
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 px-4 py-3 border-b flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <Brain className="w-5 h-5 text-blue-600" />
                Research Intelligence
              </h2>
              <div className="text-sm text-gray-600 bg-white px-2 py-1 rounded-full">
                {researchLogs.length} events
              </div>
            </div>
            
            <div className="p-4 h-80 overflow-y-auto" ref={researchLogRef}>
              {researchLogs.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Brain className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                  <p className="italic">Waiting for research to begin...</p>
                </div>
              ) : (
                researchLogs.map((log, index) => (
                  <LogEntry key={`research-${index}`} log={log} index={`research-${index}`} isResearch={true} />
                ))
              )}
            </div>

            {/* Steps Summary */}
            {researchSteps.length > 0 && (
              <div className="border-t bg-gray-50 p-3">
                <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1">
                  <Activity className="w-4 h-4" />
                  Timeline
                </h3>
                <div className="space-y-1 max-h-24 overflow-y-auto">
                  {researchSteps.map((step, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-gray-600">
                      <div className="w-2 h-2 bg-green-400 rounded-full" />
                      <span className="flex-1">{step.description}</span>
                      <span className="text-gray-400">{step.timestamp}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right: Website Links */}
          <div className="bg-white rounded-lg shadow-md border">
            <div className="bg-gradient-to-r from-orange-50 to-yellow-50 px-4 py-3 border-b flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <Link className="w-5 h-5 text-orange-600" />
                Website Links
              </h2>
              <div className="flex items-center gap-2">
                <div className="text-sm text-gray-600 bg-white px-2 py-1 rounded-full">
                  {websiteLinks.length} links
                </div>
                {websiteLinks.length > 0 && (
                  <>
                    <button
                      onClick={copyAllLinks}
                      className="text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1 px-2 py-1 rounded hover:bg-blue-50"
                      title="Copy all links"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                    <button 
                      onClick={handleClearWebsiteLinks}
                      className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1 px-2 py-1 rounded hover:bg-red-50"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </>
                )}
              </div>
            </div>
            
            <div className="p-4 h-80 overflow-y-auto" ref={linksRef}>
              {websiteLinks.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Link className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                  <p className="italic">Website links will appear here...</p>
                </div>
              ) : (
                websiteLinks.map((link, index) => (
                  <LinkEntry key={link.id} link={link} index={index} />
                ))
              )}
            </div>
            
            {/* Copy All Links Confirmation */}
            {copied['all-links'] && (
              <div className="border-t bg-green-50 p-3">
                <div className="text-sm text-green-600 text-center font-medium">
                  All {websiteLinks.length} links copied to clipboard!
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Answer Section with Integrated Chat */}
        {finalResult && (
          <div className="bg-white rounded-lg shadow-md border" data-results-section>
            <div className="bg-gradient-to-r from-green-50 to-blue-50 px-6 py-4 border-b flex justify-between items-center">
              <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
                <CheckCircle className="w-6 h-6 text-green-600" />
                Research Results
              </h2>
              <div className="flex gap-2">
                <button
                  onClick={() => handleCopy(finalResult, 'answer')}
                  className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:text-gray-800 bg-white rounded-md hover:shadow-sm transition-all"
                >
                  <Copy className="w-4 h-4" />
                  Copy
                </button>
                <a
                  href={`data:text/plain;charset=utf-8,${encodeURIComponent(finalResult)}`}
                  download="research-results.txt"
                  className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:text-gray-800 bg-white rounded-md hover:shadow-sm transition-all"
                >
                  <Download className="w-4 h-4" />
                  Download
                </a>
              </div>
            </div>
            
            <div className="p-6">
              {copied.answer && (
                <div className="mb-4 text-center text-green-600 font-medium">Results copied!</div>
              )}
              
              {/* Research Results */}
              <div className="text-gray-800 leading-relaxed mb-6">
                <ReactMarkdown 
                  components={{
                    p: ({children}) => <p className="mb-4">{children}</p>,
                    h1: ({children}) => <h1 className="text-2xl font-bold mb-4">{children}</h1>,
                    h2: ({children}) => <h2 className="text-xl font-semibold mb-3">{children}</h2>,
                    h3: ({children}) => <h3 className="text-lg font-medium mb-2">{children}</h3>,
                    ul: ({children}) => <ul className="list-disc list-inside mb-4">{children}</ul>,
                    ol: ({children}) => <ol className="list-decimal list-inside mb-4">{children}</ol>,
                    li: ({children}) => <li className="mb-1">{children}</li>,
                    code: ({children}) => <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono">{children}</code>,
                    pre: ({children}) => <pre className="bg-gray-100 p-3 rounded mb-4 overflow-x-auto">{children}</pre>,
                  }}
                >
                  {finalResult}
                </ReactMarkdown>
              </div>

              {/* Integrated Chat Section */}
              {isChatReady && (
                <>
                  <div className="border-t pt-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                        <MessageCircle className="w-5 h-5 text-blue-600" />
                        Ask Follow-up Questions
                      </h3>
                      {chatMessages.length > 0 && (
                        <button
                          onClick={() => clearChat()}
                          className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1 px-2 py-1 rounded hover:bg-red-50"
                        >
                          <Trash2 className="w-3 h-3" />
                          Clear Chat
                        </button>
                      )}
                    </div>

                    {/* Chat Messages */}
                    {chatMessages.length > 0 && (
                      <div className="max-h-96 overflow-y-auto mb-4 border rounded-lg p-4 bg-gray-50" ref={chatRef}>
                        {chatMessages.map((message, index) => (
                          <ChatMessage key={index} message={message} index={index} />
                        ))}
                        
                        {isChatLoading && (
                          <div className="flex justify-start mb-4">
                            <div className="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg rounded-bl-sm flex items-center gap-2">
                              <div className="flex space-x-1">
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                              </div>
                              <span className="text-sm">Thinking...</span>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {/* Chat Input */}
                    <div className="flex gap-3">
                      <textarea
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        onKeyPress={handleChatKeyPress}
                        placeholder="Ask me anything about these research results..."
                        className="flex-1 p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                        rows={2}
                        disabled={isChatLoading}
                      />
                      <button
                        onClick={handleChatSubmit}
                        disabled={!chatInput.trim() || isChatLoading}
                        className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-400 flex items-center gap-2 font-medium transition-colors"
                      >
                        <Send className="w-5 h-5" />
                        Send
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!finalResult && !isResearching && (
          <div className="text-center py-12 text-gray-500">
            <Search className="w-12 h-12 mx-auto mb-3 text-gray-400" />
            <h3 className="text-lg font-medium text-gray-600 mb-1">Ready to Research</h3>
            <p>Enter your question above to start an AI-powered research session.</p>
          </div>
        )}
      </div>

      {/* Custom Scrollbar Styles */}
      <style jsx>{`
        .overflow-y-auto::-webkit-scrollbar {
          width: 6px;
        }
        .overflow-y-auto::-webkit-scrollbar-track {
          background: #f1f5f9;
          border-radius: 3px;
        }
        .overflow-y-auto::-webkit-scrollbar-thumb {
          background: #cbd5e1;
          border-radius: 3px;
        }
        .overflow-y-auto::-webkit-scrollbar-thumb:hover {
          background: #94a3b8;
        }
      `}</style>
    </div>
  );
};

export default DeepResearchDashboard;

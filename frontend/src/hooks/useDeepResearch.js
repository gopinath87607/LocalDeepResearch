import { useState, useCallback, useEffect, useRef } from 'react';
import io from 'socket.io-client';

const API_BASE = 'http://localhost:8000';
const WS_BASE = 'http://localhost:8000';

export const useDeepResearch = () => {
  const [isResearching, setIsResearching] = useState(false);
  const [currentStep, setCurrentStep] = useState('');
  const [researchSteps, setResearchSteps] = useState([]);
  const [sources, setSources] = useState([]);
  const [finalResult, setFinalResult] = useState('');
  const [progress, setProgress] = useState(0);
  const [sessionId, setSessionId] = useState(null);
  const [error, setError] = useState(null);
  const [rawLogs, setRawLogs] = useState([]);
  const [groupedLogs, setGroupedLogs] = useState([]);
  const [websiteLinks, setWebsiteLinks] = useState([]);
  
  // Chat functionality
  const [isChatReady, setIsChatReady] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  
  const socketRef = useRef(null);

  const startResearch = useCallback(async (query) => {
    try {
      setError(null);
      setIsResearching(true);
      setResearchSteps([]);
      setSources([]);
      setFinalResult('');
      setProgress(0);
      setRawLogs([]);
      setGroupedLogs([]);
      setWebsiteLinks([]);
      
      // Reset chat state
      setIsChatReady(false);
      setChatMessages([]);
      setIsChatLoading(false);

      const response = await fetch(`${API_BASE}/api/research/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to start research');
      }

      const { session_id } = await response.json();
      setSessionId(session_id);

      // SocketIO connection
      socketRef.current = io(WS_BASE, { 
        transports: ['websocket', 'polling'],  
        autoConnect: true 
      });

      socketRef.current.emit('join_session', { session_id });

      socketRef.current.on('research_update', (update) => {
        handleSocketUpdate(update);
      });

      socketRef.current.on('connect_error', (err) => {
        console.error('SocketIO connect error:', err);
        if (!socketRef.current.connected) {
          setError('Connection error occurred');
          setIsResearching(false);
        }
      });

      socketRef.current.on('connect', () => {
        console.log('SocketIO connected successfully');
        setError(null);
      });

      socketRef.current.on('disconnect', () => {
        console.log('SocketIO disconnected');
        setIsResearching(false);
      });

    } catch (err) {
      console.error('Start research error:', err);
      setError(err.message);
      setIsResearching(false);
    }
  }, []);

  const sendChatMessage = useCallback(async (message) => {
    if (!sessionId || !message.trim() || isChatLoading) return;

    const userMessage = {
      role: 'user',
      content: message.trim(),
      timestamp: new Date().toLocaleTimeString()
    };

    // Add user message immediately
    setChatMessages(prev => [...prev, userMessage]);
    setIsChatLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/chat/send`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: message.trim()
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

    } catch (err) {
      console.error('Chat send error:', err);
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error sending your message. Please try again.',
        timestamp: new Date().toLocaleTimeString()
      }]);
      setIsChatLoading(false);
    }
  }, [sessionId, isChatLoading]);

  const handleSocketUpdate = (update) => {
    switch (update.type) {
      case 'research_started':
        setCurrentStep('Research session started');
        setRawLogs(prev => [...prev, { 
          type: 'info', 
          content: `Researching: "${update.query}"`, 
          timestamp: new Date().toLocaleTimeString() 
        }]);
        break;

      case 'step_start':
        setCurrentStep(update.step.description);
        setProgress(update.progress);
        setResearchSteps(prev => [...prev, {
          ...update.step,
          timestamp: new Date().toLocaleTimeString(),
          status: 'completed'
        }]);
        break;

      case 'research_complete':
        setFinalResult(update.result);
        setCurrentStep('Research completed');
        setIsResearching(false);
        setProgress(100);
        break;

      case 'chat_ready':
        setIsChatReady(true);
        setChatMessages(prev => [...prev, {
          role: 'system',
          content: update.message,
          timestamp: new Date().toLocaleTimeString()
        }]);
        break;

      case 'chat_response':
        setIsChatLoading(false);
        setChatMessages(prev => [...prev, {
          role: 'assistant',
          content: update.message,
          timestamp: update.timestamp
        }]);
        break;

      case 'chat_error':
        setIsChatLoading(false);
        setChatMessages(prev => [...prev, {
          role: 'assistant',
          content: update.message,
          timestamp: new Date().toLocaleTimeString()
        }]);
        break;

      case 'error':
        setError(update.message);
        setIsResearching(false);
        setIsChatLoading(false);
        break;

      // Handle URL events from backend
      case 'url_found':
      case 'url_visited':
        const urlInfo = update.url_info;
        setWebsiteLinks(prev => {
          const exists = prev.some(link => link.url === urlInfo.url);
          if (!exists) {
            return [...prev, {
              ...urlInfo,
              id: Date.now() + Math.random(),
              source: update.type
            }];
          }
          return prev;
        });
        break;

      // Research intelligence updates
      case 'react_thought':
      case 'react_action':
      case 'research_details':
      case 'research_log':
        const newLog = { 
          type: update.type, 
          content: update.content, 
          timestamp: new Date().toLocaleTimeString() 
        };
        setRawLogs(prev => [...prev, newLog]);
        break;

      // Server status updates
      case 'server_status':
        const serverLog = { 
          type: 'server_status', 
          content: update.content, 
          timestamp: new Date().toLocaleTimeString() 
        };
        setRawLogs(prev => [...prev, serverLog]);
        break;

      default:
        console.log('Unknown update type:', update.type);
    }
  };

  // Keep the grouping logic
  useEffect(() => {
    if (rawLogs.length > 0) {
      groupLogs(rawLogs);
    }
  }, [rawLogs]);

  const groupLogs = (logs) => {
    const grouped = [];
    
    // Separate research intelligence from server status
    const researchLogs = logs.filter(log => 
      ['react_thought', 'react_action', 'research_details', 'research_log'].includes(log.type)
    );
    const serverLogs = logs.filter(log => 
      ['server_status', 'info'].includes(log.type)
    );
    
    // Add server logs as 'misc' group (what UI expects)
    if (serverLogs.length > 0) {
      grouped.push({ round: 'misc', items: serverLogs });
    }
    
    // Group research intelligence by rounds or as single group
    if (researchLogs.length > 0) {
      let currentRound = 1;
      let currentGroup = { round: `Research Round ${currentRound}`, items: [] };
      
      researchLogs.forEach((log) => {
        // Check if this starts a new round
        if (log.content.includes('Round') && log.content.includes(':')) {
          if (currentGroup.items.length > 0) {
            grouped.push({ ...currentGroup });
          }
          const roundMatch = log.content.match(/Round (\d+)/);
          if (roundMatch) {
            currentRound = parseInt(roundMatch[1]);
          }
          currentGroup = { round: `Research Round ${currentRound}`, items: [log] };
        } else {
          currentGroup.items.push(log);
        }
      });
      
      if (currentGroup.items.length > 0) {
        grouped.push(currentGroup);
      }
    }
    
    setGroupedLogs(grouped);
  };

  // Cleanup socket on unmount
  useEffect(() => {
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []);

  return {
    startResearch,
    isResearching,
    currentStep,
    researchSteps,
    sources,
    finalResult,
    progress,
    sessionId,
    error,
    groupedLogs,
    websiteLinks,
    
    // Chat functionality
    isChatReady,
    chatMessages,
    isChatLoading,
    sendChatMessage,
    
    clearLogs: () => {
      setRawLogs([]);
      setGroupedLogs([]);
    },
    clearWebsiteLinks: () => {
      setWebsiteLinks([]);
    },
    clearChat: () => {
      setChatMessages([]);
    }
  };
};

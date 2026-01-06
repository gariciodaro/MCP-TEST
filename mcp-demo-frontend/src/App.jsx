import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

const API_BASE = 'http://localhost:8000'
const WS_BASE = 'ws://localhost:8000'

function App() {
  const [connected, setConnected] = useState(false)
  const [serverPath, setServerPath] = useState('F:\\my-code\\MCP-TEST\\weather-mcp-server\\weather.py')
  const [tools, setTools] = useState([])
  const [resources, setResources] = useState([])
  const [prompts, setPrompts] = useState([])
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('chat')
  const [selectedResource, setSelectedResource] = useState(null)
  const [resourceContent, setResourceContent] = useState(null)
  const [loadingResource, setLoadingResource] = useState(false)
  const [selectedPrompt, setSelectedPrompt] = useState(null)
  const [promptArgs, setPromptArgs] = useState({})
  const [loadingPrompt, setLoadingPrompt] = useState(false)
  const [promptPreview, setPromptPreview] = useState(null)
  const messagesEndRef = useRef(null)
  const wsRef = useRef(null)
  const usePromptDirectlyRef = useRef(false)  // Track if we should use prompt directly
  
  // Elicitation modal state
  const [showElicitation, setShowElicitation] = useState(false)
  const [elicitationData, setElicitationData] = useState(null)
  const [elicitationForm, setElicitationForm] = useState({})
  
  // Sampling modal state
  const [showSampling, setShowSampling] = useState(false)
  const [samplingData, setSamplingData] = useState(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    checkStatus()
  }, [])

  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`)
      const data = await res.json()
      setConnected(data.connected)
      if (data.connected) {
        setTools(data.tools || [])
        setResources(data.resources || [])
        setPrompts(data.prompts || [])
      }
    } catch (err) {
      console.error('Failed to check status:', err)
    }
  }

  const connect = async () => {
    setLoading(true)
    
    // Create WebSocket connection
    const ws = new WebSocket(`${WS_BASE}/ws/chat`)
    wsRef.current = ws
    
    ws.onopen = () => {
      // Send connect message with server path
      ws.send(JSON.stringify({
        type: 'connect',
        server_path: serverPath
      }))
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      console.log('WebSocket message:', data)
      
      switch (data.type) {
        case 'connected':
          setConnected(true)
          setTools(data.tools || [])
          setResources(data.resources || [])
          setPrompts(data.prompts || [])
          setMessages([{ 
            role: 'system', 
            content: `Connected to MCP server. Available tools: ${(data.tools || []).map(t => t.name).join(', ')}` 
          }])
          setLoading(false)
          break
          
        case 'elicitation':
          // Show elicitation modal
          setElicitationData({
            message: data.message,
            schema: data.schema
          })
          setElicitationForm({})
          setShowElicitation(true)
          break
          
        case 'sampling_request':
          // Show sampling approval modal
          setSamplingData({
            messages: data.messages,
            system_prompt: data.system_prompt,
            max_tokens: data.max_tokens
          })
          setShowSampling(true)
          break
          
        case 'response':
          // Handle normal chat response
          if (data.tool_calls && data.tool_calls.length > 0) {
            for (const tc of data.tool_calls) {
              setMessages(prev => [...prev, {
                role: 'tool',
                name: tc.name,
                arguments: tc.arguments,
                result: tc.result
              }])
            }
          }
          if (data.content) {
            setMessages(prev => [...prev, { role: 'assistant', content: data.content }])
          }
          setLoading(false)
          break
        
        case 'resource_content':
          // Handle resource read response
          if (data.error) {
            setResourceContent(`Error: ${data.error}`)
          } else {
            setResourceContent(data.content || '')
          }
          setLoadingResource(false)
          break
        
        case 'prompt_content':
          // Handle prompt get response
          if (data.error) {
            alert(`Failed to get prompt: ${data.error}`)
          } else if (data.messages && data.messages.length > 0) {
            const userMsg = data.messages.find(m => m.role === 'user')
            if (userMsg) {
              if (usePromptDirectlyRef.current) {
                // "Use Prompt" was clicked - go directly to chat
                setInputMessage(userMsg.content)
                setActiveTab('chat')
                setSelectedPrompt(null)
                setPromptArgs({})
                setPromptPreview(null)
                usePromptDirectlyRef.current = false
              } else {
                // "Preview" was clicked - just show preview
                setPromptPreview(userMsg.content)
              }
            }
          }
          setLoadingPrompt(false)
          break
          
        case 'error':
          setMessages(prev => [...prev, { role: 'error', content: data.message || data.detail }])
          setLoading(false)
          setLoadingResource(false)
          setLoadingPrompt(false)
          break
          
        default:
          console.warn('Unknown message type:', data.type)
      }
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setMessages(prev => [...prev, { role: 'error', content: 'WebSocket connection error' }])
      setLoading(false)
    }
    
    ws.onclose = () => {
      console.log('WebSocket closed')
      setConnected(false)
      setShowElicitation(false)
      setShowSampling(false)
      wsRef.current = null
    }
  }

  const disconnect = async () => {
    setLoading(true)
    
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'disconnect' }))
      wsRef.current.close()
      wsRef.current = null
    }
    
    setConnected(false)
    setTools([])
    setResources([])
    setPrompts([])
    setMessages([])
    setShowElicitation(false)
    setShowSampling(false)
    setLoading(false)
  }

  const sendMessage = async () => {
    if (!inputMessage.trim() || !connected || !wsRef.current) return

    const userMessage = { role: 'user', content: inputMessage }
    setMessages(prev => [...prev, userMessage])
    const msgToSend = inputMessage
    setInputMessage('')
    setLoading(true)

    // Send via WebSocket
    wsRef.current.send(JSON.stringify({
      type: 'chat',
      message: msgToSend
    }))
  }
  
  // Elicitation handlers
  const handleElicitationSubmit = () => {
    if (!wsRef.current) return
    
    wsRef.current.send(JSON.stringify({
      type: 'elicitation_response',
      action: 'accept',
      data: elicitationForm
    }))
    
    setMessages(prev => [...prev, { 
      role: 'system', 
      content: `✅ Provided information: ${JSON.stringify(elicitationForm, null, 2)}` 
    }])
    setShowElicitation(false)
    setElicitationData(null)
    setElicitationForm({})
  }
  
  const handleElicitationDecline = () => {
    if (!wsRef.current) return
    
    wsRef.current.send(JSON.stringify({
      type: 'elicitation_response',
      action: 'decline'
    }))
    
    setMessages(prev => [...prev, { role: 'system', content: '❌ Declined to provide information' }])
    setShowElicitation(false)
    setElicitationData(null)
    setElicitationForm({})
    setLoading(false)
  }
  
  const handleElicitationCancel = () => {
    if (!wsRef.current) return
    
    wsRef.current.send(JSON.stringify({
      type: 'elicitation_response',
      action: 'cancel'
    }))
    
    setMessages(prev => [...prev, { role: 'system', content: '⏹️ Cancelled operation' }])
    setShowElicitation(false)
    setElicitationData(null)
    setElicitationForm({})
    setLoading(false)
  }
  
  // Sampling handlers
  const handleSamplingApprove = () => {
    if (!wsRef.current) return
    
    wsRef.current.send(JSON.stringify({
      type: 'sampling_response',
      approved: true,
      response: null  // Let the client call the LLM
    }))
    
    setMessages(prev => [...prev, { 
      role: 'system', 
      content: '✅ Approved LLM sampling request - generating response...' 
    }])
    setShowSampling(false)
    setSamplingData(null)
  }
  
  const handleSamplingReject = () => {
    if (!wsRef.current) return
    
    wsRef.current.send(JSON.stringify({
      type: 'sampling_response',
      approved: false
    }))
    
    setMessages(prev => [...prev, { 
      role: 'system', 
      content: '❌ Rejected LLM sampling request' 
    }])
    setShowSampling(false)
    setSamplingData(null)
    setLoading(false)
  }
  
  const updateElicitationField = (fieldName, value) => {
    setElicitationForm(prev => ({
      ...prev,
      [fieldName]: value
    }))
  }
  
  // Render form fields from JSON schema
  const renderElicitationFields = () => {
    if (!elicitationData?.schema?.properties) return null
    
    const schema = elicitationData.schema
    const properties = schema.properties || {}
    const required = schema.required || []
    
    return Object.entries(properties).map(([fieldName, fieldSchema]) => {
      const isRequired = required.includes(fieldName)
      const fieldType = fieldSchema.type || 'string'
      
      return (
        <div key={fieldName} className="elicitation-field">
          <label htmlFor={`elicit-${fieldName}`}>
            {fieldSchema.title || fieldName}
            {isRequired && <span className="required">*</span>}
          </label>
          {fieldSchema.description && (
            <span className="field-description">{fieldSchema.description}</span>
          )}
          {fieldType === 'integer' || fieldType === 'number' ? (
            <input
              id={`elicit-${fieldName}`}
              type="number"
              value={elicitationForm[fieldName] || ''}
              onChange={(e) => updateElicitationField(fieldName, parseInt(e.target.value) || 0)}
              placeholder={`Enter ${fieldName}...`}
            />
          ) : fieldType === 'boolean' ? (
            <select
              id={`elicit-${fieldName}`}
              value={elicitationForm[fieldName] !== undefined ? String(elicitationForm[fieldName]) : ''}
              onChange={(e) => updateElicitationField(fieldName, e.target.value === 'true')}
            >
              <option value="">Select...</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          ) : fieldSchema.enum ? (
            <select
              id={`elicit-${fieldName}`}
              value={elicitationForm[fieldName] || ''}
              onChange={(e) => updateElicitationField(fieldName, e.target.value)}
            >
              <option value="">Select...</option>
              {fieldSchema.enum.map(opt => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          ) : (
            <input
              id={`elicit-${fieldName}`}
              type="text"
              value={elicitationForm[fieldName] || ''}
              onChange={(e) => updateElicitationField(fieldName, e.target.value)}
              placeholder={`Enter ${fieldName}...`}
            />
          )}
        </div>
      )
    })
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const readResource = async (uri) => {
    if (!wsRef.current) return
    
    setLoadingResource(true)
    setSelectedResource(uri)
    setResourceContent(null)
    
    // Send via WebSocket
    wsRef.current.send(JSON.stringify({
      type: 'read_resource',
      uri: uri
    }))
  }

  const closeResourceModal = () => {
    setSelectedResource(null)
    setResourceContent(null)
  }

  const selectPrompt = (prompt) => {
    setSelectedPrompt(prompt)
    // Initialize arguments with empty strings
    const args = {}
    if (prompt.arguments) {
      prompt.arguments.forEach(arg => {
        args[arg.name] = ''
      })
    }
    setPromptArgs(args)
  }

  const closePromptModal = () => {
    setSelectedPrompt(null)
    setPromptArgs({})
    setPromptPreview(null)
  }

  const updatePromptArg = (name, value) => {
    setPromptArgs(prev => ({ ...prev, [name]: value }))
    setPromptPreview(null) // Clear preview when args change
  }

  const previewPrompt = async () => {
    if (!selectedPrompt || !wsRef.current) return
    
    setLoadingPrompt(true)
    usePromptDirectlyRef.current = false  // Just preview, don't use
    
    // Send via WebSocket
    wsRef.current.send(JSON.stringify({
      type: 'get_prompt',
      name: selectedPrompt.name,
      arguments: promptArgs
    }))
  }

  const usePrompt = async () => {
    if (promptPreview) {
      // Use existing preview
      setInputMessage(promptPreview)
      setActiveTab('chat')
      closePromptModal()
      return
    }
    
    // No preview yet, fetch via WebSocket first
    if (!selectedPrompt || !wsRef.current) return
    
    // Request the prompt - mark that we want to use it directly
    setLoadingPrompt(true)
    usePromptDirectlyRef.current = true
    
    wsRef.current.send(JSON.stringify({
      type: 'get_prompt',
      name: selectedPrompt.name,
      arguments: promptArgs
    }))
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <h1>🔌 MCP Demo</h1>
          <span className={`status-badge ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '● Connected' : '○ Disconnected'}
          </span>
        </div>
        <div className="header-right">
          <input
            type="text"
            value={serverPath}
            onChange={(e) => setServerPath(e.target.value)}
            placeholder="Path to MCP server script"
            className="server-input"
            disabled={connected}
          />
          <button 
            onClick={connected ? disconnect : connect}
            disabled={loading}
            className={`btn ${connected ? 'btn-danger' : 'btn-primary'}`}
          >
            {loading ? '...' : (connected ? 'Disconnect' : 'Connect')}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="main-content">
        {/* Sidebar */}
        <aside className="sidebar">
          <nav className="tabs">
            <button 
              className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              💬 Chat
            </button>
            <button 
              className={`tab ${activeTab === 'tools' ? 'active' : ''}`}
              onClick={() => setActiveTab('tools')}
            >
              🔧 Tools ({tools.length})
            </button>
            <button 
              className={`tab ${activeTab === 'resources' ? 'active' : ''}`}
              onClick={() => setActiveTab('resources')}
            >
              📦 Resources ({resources.length})
            </button>
            <button 
              className={`tab ${activeTab === 'prompts' ? 'active' : ''}`}
              onClick={() => setActiveTab('prompts')}
            >
              📝 Prompts ({prompts.length})
            </button>
          </nav>

          {/* Sidebar Content */}
          <div className="sidebar-content">
            {activeTab === 'tools' && (
              <div className="tools-list">
                <h3>Available Tools</h3>
                {tools.length === 0 ? (
                  <p className="empty-state">No tools available. Connect to a server first.</p>
                ) : (
                  tools.map((tool, idx) => (
                    <div key={idx} className="tool-card">
                      <div className="tool-name">{tool.name}</div>
                      <div className="tool-description">{tool.description}</div>
                      {tool.input_schema?.properties && (
                        <div className="tool-params">
                          <strong>Parameters:</strong>
                          <ul>
                            {Object.entries(tool.input_schema.properties).map(([name, schema]) => (
                              <li key={name}>
                                <code>{name}</code>: {schema.type}
                                {schema.description && ` - ${schema.description}`}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'resources' && (
              <div className="resources-list">
                <h3>Available Resources</h3>
                <p className="resources-hint">Click a resource to read its content</p>
                {resources.length === 0 ? (
                  <p className="empty-state">No resources available.</p>
                ) : (
                  resources.map((res, idx) => (
                    <div 
                      key={idx} 
                      className="resource-card clickable"
                      onClick={() => readResource(res.uri)}
                    >
                      <div className="resource-uri">{res.uri}</div>
                      <div className="resource-name">{res.name}</div>
                      {res.description && <div className="resource-description">{res.description}</div>}
                      <div className="resource-action">📖 Click to read</div>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'prompts' && (
              <div className="prompts-list">
                <h3>Available Prompts</h3>
                <p className="prompts-hint">Click a prompt to use it</p>
                {prompts.length === 0 ? (
                  <p className="empty-state">No prompts available.</p>
                ) : (
                  prompts.map((prompt, idx) => (
                    <div 
                      key={idx} 
                      className="prompt-card clickable"
                      onClick={() => selectPrompt(prompt)}
                    >
                      <div className="prompt-name">{prompt.name}</div>
                      {prompt.description && <div className="prompt-description">{prompt.description}</div>}
                      {prompt.arguments && prompt.arguments.length > 0 && (
                        <div className="prompt-args-preview">
                          <strong>Arguments:</strong> {prompt.arguments.map(a => a.name).join(', ')}
                        </div>
                      )}
                      <div className="prompt-action">📝 Click to use</div>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'chat' && (
              <div className="chat-info">
                <h3>MCP Chat Demo</h3>
                <p>Ask questions about weather to see MCP tools in action!</p>
                <div className="example-queries">
                  <h4>Try asking:</h4>
                  <ul>
                    <li>"What's the weather forecast for latitude 40.7, longitude -74.0?"</li>
                    <li>"Are there any weather alerts in CA?"</li>
                    <li>"Get the forecast for NYC (40.7128, -74.0060)"</li>
                    <li><strong>"Plan a trip to New York"</strong> - <em>Try this to see elicitation!</em></li>
                    <li><strong>"Analyze weather patterns for New York, Los Angeles, Chicago"</strong> - <em>Try this to see sampling!</em></li>
                  </ul>
                </div>
              </div>
            )}
          </div>
        </aside>

        {/* Chat Area */}
        <main className="chat-area">
          <div className="messages">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message ${msg.role}`}>
                {msg.role === 'user' && (
                  <div className="message-content user-message">
                    <span className="message-icon">👤</span>
                    <div className="message-text">{msg.content}</div>
                  </div>
                )}
                {msg.role === 'assistant' && (
                  <div className="message-content assistant-message">
                    <span className="message-icon">🤖</span>
                    <div className="message-text markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                )}
                {msg.role === 'tool' && (
                  <div className="message-content tool-message">
                    <span className="message-icon">🔧</span>
                    <div className="tool-call-info">
                      <div className="tool-call-header">
                        Tool Call: <code>{msg.name}</code>
                      </div>
                      <div className="tool-call-args">
                        <strong>Arguments:</strong>
                        <pre>{JSON.stringify(msg.arguments, null, 2)}</pre>
                      </div>
                      <div className="tool-call-result">
                        <strong>Result:</strong>
                        <pre>{msg.result}</pre>
                      </div>
                    </div>
                  </div>
                )}
                {msg.role === 'system' && (
                  <div className="message-content system-message">
                    <span className="message-icon">ℹ️</span>
                    <div className="message-text">{msg.content}</div>
                  </div>
                )}
                {msg.role === 'error' && (
                  <div className="message-content error-message">
                    <span className="message-icon">❌</span>
                    <div className="message-text">{msg.content}</div>
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="message loading">
                <div className="message-content">
                  <span className="loading-dots">⏳ Processing...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="input-area">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={connected ? "Type a message..." : "Connect to an MCP server first"}
              disabled={!connected || loading}
              rows={2}
            />
            <button 
              onClick={sendMessage} 
              disabled={!connected || loading || !inputMessage.trim()}
              className="btn btn-primary send-btn"
            >
              Send
            </button>
          </div>
        </main>
      </div>

      {/* Resource Modal */}
      {selectedResource && (
        <div className="modal-overlay" onClick={closeResourceModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📦 Resource Content</h2>
              <button className="modal-close" onClick={closeResourceModal}>✕</button>
            </div>
            <div className="modal-uri">{selectedResource}</div>
            <div className="modal-content">
              {loadingResource ? (
                <div className="loading-resource">Loading resource...</div>
              ) : (
                <pre>{resourceContent}</pre>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Prompt Modal */}
      {selectedPrompt && (
        <div className="modal-overlay" onClick={closePromptModal}>
          <div className="modal prompt-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📝 Use Prompt</h2>
              <button className="modal-close" onClick={closePromptModal}>✕</button>
            </div>
            <div className="prompt-modal-name">{selectedPrompt.name}</div>
            {selectedPrompt.description && (
              <div className="prompt-modal-description">{selectedPrompt.description}</div>
            )}
            
            {selectedPrompt.arguments && selectedPrompt.arguments.length > 0 ? (
              <div className="prompt-args-form">
                <h4>Fill in the arguments:</h4>
                {selectedPrompt.arguments.map((arg, idx) => (
                  <div key={idx} className="prompt-arg-field">
                    <label htmlFor={`arg-${arg.name}`}>
                      {arg.name}
                      {arg.required && <span className="required">*</span>}
                    </label>
                    {arg.description && (
                      <span className="arg-description">{arg.description}</span>
                    )}
                    <input
                      id={`arg-${arg.name}`}
                      type="text"
                      value={promptArgs[arg.name] || ''}
                      onChange={(e) => updatePromptArg(arg.name, e.target.value)}
                      placeholder={`Enter ${arg.name}...`}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-args-message">This prompt has no arguments.</p>
            )}

            {promptPreview && (
              <div className="prompt-preview">
                <h4>Preview:</h4>
                <div className="prompt-preview-content markdown-content">
                  <ReactMarkdown>{promptPreview}</ReactMarkdown>
                </div>
              </div>
            )}
            
            <div className="prompt-modal-actions">
              <button 
                className="btn btn-secondary" 
                onClick={closePromptModal}
              >
                Cancel
              </button>
              <button 
                className="btn btn-outline" 
                onClick={previewPrompt}
                disabled={loadingPrompt}
              >
                {loadingPrompt ? 'Loading...' : '👁️ Preview'}
              </button>
              <button 
                className="btn btn-primary" 
                onClick={usePrompt}
                disabled={loadingPrompt}
              >
                {promptPreview ? 'Use Prompt' : 'Use Prompt'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Elicitation Modal */}
      {showElicitation && elicitationData && (
        <div className="modal-overlay elicitation-overlay">
          <div className="modal elicitation-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header elicitation-header">
              <h2>🤖 Additional Information Needed</h2>
            </div>
            
            <div className="elicitation-message">
              <p>{elicitationData.message || 'The tool needs more information to continue:'}</p>
            </div>
            
            <div className="elicitation-form">
              {renderElicitationFields()}
            </div>
            
            <div className="elicitation-actions">
              <button 
                className="btn btn-secondary" 
                onClick={handleElicitationCancel}
              >
                Cancel
              </button>
              <button 
                className="btn btn-outline" 
                onClick={handleElicitationDecline}
              >
                Decline
              </button>
              <button 
                className="btn btn-primary" 
                onClick={handleElicitationSubmit}
              >
                Submit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sampling Modal */}
      {showSampling && samplingData && (
        <div className="modal-overlay sampling-overlay">
          <div className="modal sampling-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header sampling-header">
              <h2>🔮 LLM Request from Server</h2>
            </div>
            
            <div className="sampling-message">
              <p>The MCP server is requesting your AI to generate a response.</p>
              <p className="sampling-description">
                <strong>This is MCP Sampling:</strong> The server needs AI assistance 
                to process data or make decisions. Review the request below and 
                approve if you want the AI to respond.
              </p>
            </div>
            
            <div className="sampling-details">
              {samplingData.system_prompt && (
                <div className="sampling-section">
                  <label>System Prompt:</label>
                  <pre>{samplingData.system_prompt}</pre>
                </div>
              )}
              
              <div className="sampling-section">
                <label>Messages ({samplingData.messages.length}):</label>
                <div className="sampling-messages">
                  {samplingData.messages.map((msg, idx) => (
                    <div key={idx} className={`sampling-msg ${msg.role}`}>
                      <span className="msg-role">{msg.role}:</span>
                      <pre>{msg.content}</pre>
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="sampling-section">
                <label>Max Tokens: {samplingData.max_tokens}</label>
              </div>
            </div>
            
            <div className="sampling-actions">
              <button 
                className="btn btn-secondary" 
                onClick={handleSamplingReject}
              >
                ❌ Reject
              </button>
              <button 
                className="btn btn-primary" 
                onClick={handleSamplingApprove}
              >
                ✅ Approve & Generate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
